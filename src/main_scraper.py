import logging
import sys
import time
from db import get_db_connection

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

# --- Configurações ---
URL_ALVO = "https://ridigital.org.br/CartorioNacional/CartorioNacional.aspx"
TABLE_NAME = "cartorios_enriquecidos"
LOG_FILE = "logs/scraper.log"
DEFAULT_NOT_FOUND_TEXT = "Não informado"

# --- Configuração do Logging ---
# Configura um logger para registrar sucessos e falhas em um arquivo.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8"),
        logging.StreamHandler(),  # Também exibe os logs no console
    ],
)


def get_pending_cns():
    """Busca no banco de dados os CNS que ainda não foram processados."""
    conn = get_db_connection()
    if not conn:
        logging.critical("Não foi possível conectar ao banco para buscar tarefas.")
        sys.exit(1)

    try:
        with conn.cursor() as cursor:
            # A lógica de "resumível": pegamos apenas onde o NomeCartorio é nulo.
            # Isso indica que o enriquecimento ainda não ocorreu.
            cursor.execute(
                f"SELECT CNS FROM {TABLE_NAME} WHERE NomeCartorio IS NULL OR NomeCartorio = ''"
            )
            cns_list = [row.CNS for row in cursor.fetchall()]
            logging.info(f"Encontrados {len(cns_list)} CNS pendentes de processamento.")
            return cns_list
    except Exception as e:
        logging.error(f"Erro ao buscar CNS pendentes: {e}")
        return []
    finally:
        if conn:
            conn.close()


def extract_element_text(driver, by, value, default=DEFAULT_NOT_FOUND_TEXT):
    """Função auxiliar para extrair texto de um elemento de forma segura."""
    try:
        text = driver.find_element(by, value).text.strip()
        return text if text else default  # Retorna o default se o texto for vazio
    except NoSuchElementException:
        return default


def scrape_cns_data(driver, cns):
    """Executa o scraping para um único CNS e retorna um dicionário com os dados."""
    driver.get(URL_ALVO)

    # Digita o CNS e espera o painel de informações aparecer
    input_cns = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, '//*[@id="txtListaCartoriosCNS"]'))
    )
    input_cns.clear()
    input_cns.send_keys(cns)

    # Espera explícita pela visibilidade do painel de resultados. Essencial!
    WebDriverWait(driver, 15).until(
        EC.visibility_of_element_located(
            (By.XPATH, '//*[@id="panelDadosCartorio"]/div')
        )
    )

    # Extração dos dados usando os XPaths fornecidos
    data = {}
    data["NomeCartorio"] = extract_element_text(driver, By.XPATH, '//*[@id="lblRazao"]')
    data["Tabeliao"] = extract_element_text(
        driver, By.XPATH, '//*[@id="lblResponsavel"]'
    )

    # Concatenação de endereço
    logradouro = extract_element_text(driver, By.XPATH, '//*[@id="lblLogradouro"]')
    numero = extract_element_text(driver, By.XPATH, '//*[@id="lblNumero"]')
    complemento = extract_element_text(driver, By.XPATH, '//*[@id="lblComplemento"]')
    bairro = extract_element_text(driver, By.XPATH, '//*[@id="lblBairro"]')

    # Monta o endereço apenas com as partes que existem
    address_parts = [logradouro, numero, complemento, bairro]
    # Filtra para não incluir "Não informado" na string final
    valid_parts = [part for part in address_parts if part != DEFAULT_NOT_FOUND_TEXT]
    data["Endereco"] = ", ".join(valid_parts) if valid_parts else DEFAULT_NOT_FOUND_TEXT

    data["CEP"] = extract_element_text(driver, By.XPATH, '//*[@id="lblCep"]')

    # Concatenação de telefone
    ddd = extract_element_text(driver, By.XPATH, '//*[@id="lblDDDTelefone"]')
    telefone_num = extract_element_text(driver, By.XPATH, '//*[@id="lblTelefone"]')

    if ddd != DEFAULT_NOT_FOUND_TEXT and telefone_num != DEFAULT_NOT_FOUND_TEXT:
        data["Telefone"] = f"({ddd}) {telefone_num}"
    else:
        data["Telefone"] = DEFAULT_NOT_FOUND_TEXT

    data["Email"] = extract_element_text(driver, By.XPATH, '//*[@id="lblEmail"]')

    # Para 'Site' e 'Atribuições', o texto vem após o <b>. O XPath precisa ser ajustado.
    # XPath para pegar o nó de texto seguinte a um elemento <b> específico.
    site_text = extract_element_text(
        driver, By.XPATH, '//*[@id="panelDadosCartorio"]/div/ul/li[6]'
    )
    if "Site:" in site_text:
        data["Site"] = site_text.replace("Site:", "").strip()
    else:
        data["Site"] = (
            site_text  # Se não encontrar o "Site:", pode ser o próprio valor ou "Não informado"
        )

    atribuicoes_text = extract_element_text(
        driver, By.XPATH, '//*[@id="panelDadosCartorio"]/div/ul/li[7]'
    )
    if "Serviços ativados ao cartório:" in atribuicoes_text:
        data["Atribuicoes"] = atribuicoes_text.replace(
            "Serviços ativados ao cartório:", ""
        ).strip()
    else:
        data["Atribuicoes"] = atribuicoes_text

    # Extrai a UF do próprio nome do cartório ou de outro campo se disponível
    # Exemplo: "7º OFICIAL DE REGISTRO DE IMÓVEIS DA COMARCA DE CURITIBA - PR"
    nome_cartorio = data.get("NomeCartorio", "")
    if " - " in nome_cartorio:
        data["UF"] = nome_cartorio.split(" - ")[-1]
    else:
        data["UF"] = ""

    return data


def update_cartorio_data(cns, data):
    """Atualiza um registro no banco de dados com os dados extraídos."""
    conn = get_db_connection()
    if not conn:
        logging.error(f"CNS {cns}: Falha ao conectar no banco para salvar dados.")
        return False

    # Prepara o SQL UPDATE dinamicamente
    # Filtra chaves com valores nulos ou vazios para não sobrescrever dados existentes com nada
    update_data = {k: v for k, v in data.items() if v}
    if not update_data:
        logging.warning(f"CNS {cns}: Nenhum dado novo para atualizar.")
        return True  # Considera sucesso pois não há o que fazer

    set_clause = ", ".join([f"{key} = ?" for key in update_data.keys()])
    sql = (
        f"UPDATE {TABLE_NAME} SET {set_clause}, data_extracao = GETDATE() WHERE CNS = ?"
    )
    params = list(update_data.values()) + [cns]

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
        conn.commit()
        logging.info(f"CNS {cns}: Dados salvos com sucesso.")
        return True
    except Exception as e:
        logging.error(f"CNS {cns}: Erro ao salvar no banco: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def main():
    """Função principal que orquestra o processo de scraping."""
    cns_list = get_pending_cns()
    total = len(cns_list)

    if total == 0:
        logging.info("Nenhum CNS para processar. Trabalho concluído.")
        return

    # Configura o WebDriver (Selenium 4+ gerencia o driver automaticamente)
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless") # Descomente para rodar sem abrir janela do navegador

    driver = None  # Inicializa o driver como None fora do loop

    for i, cns in enumerate(cns_list):
        try:
            # Se o driver não existe (primeira execução ou após uma falha), crie um novo.
            if driver is None:
                logging.info("Iniciando uma nova instância do navegador...")
                driver = webdriver.Chrome(options=options)

            logging.info(f"--- Processando {i+1}/{total}: CNS {cns} ---")
            scraped_data = scrape_cns_data(driver, cns)

            # Validação mínima: se não achou nome, algo deu errado.
            if (
                not scraped_data.get("NomeCartorio")
                or scraped_data.get("NomeCartorio") == DEFAULT_NOT_FOUND_TEXT
            ):
                raise ValueError("Extração falhou, Nome do Cartório não encontrado.")

            update_cartorio_data(cns, scraped_data)
            time.sleep(
                1
            )  # Pausa de cortesia menor, pois não estamos reiniciando o browser

        except (TimeoutException, WebDriverException, ValueError) as e:
            logging.error(
                f"CNS {cns}: Falha no processamento. Causa: {e}. O navegador será reiniciado."
            )
            if driver:
                driver.quit()
            driver = None  # Marca o driver como "morto" para ser recriado na próxima iteração
            time.sleep(5)  # Pausa maior após uma falha para estabilizar
        except Exception as e:
            logging.critical(
                f"CNS {cns}: Erro crítico não relacionado ao WebDriver. Causa: {e}"
            )
            # Em um erro muito grave, podemos decidir parar ou apenas reiniciar o driver
            if driver:
                driver.quit()
            driver = None
            time.sleep(5)

    # Garante que a última instância do navegador seja fechada ao final do processo
    if driver:
        logging.info("--- FIM DO PROCESSAMENTO --- Fechando navegador.")
        driver.quit()
    else:
        logging.info("--- FIM DO PROCESSAMENTO ---")


if __name__ == "__main__":
    main()
