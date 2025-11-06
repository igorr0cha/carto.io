import logging
import sys
import time
from collections import defaultdict
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
    UnexpectedAlertPresentException,  # Mais específico para alertas
)

# --- Configurações ---
URL_ALVO = "https://ridigital.org.br/CartorioNacional/CartorioNacional.aspx"
TABLE_NAME = "cartorios_enriquecidos"
LOG_FILE = "logs/scraper.log"
DEFAULT_NOT_FOUND_TEXT = "Não informado"
STATUS_CNS_NOT_FOUND = "CNS NÃO ENCONTRADO NO SITE"
MAX_RETRIES = 3

# Novo: Set com todas as UFs do Brasil para validação
UFS_BRASIL = {
    "AC",
    "AL",
    "AP",
    "AM",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MT",
    "MS",
    "MG",
    "PA",
    "PB",
    "PR",
    "PE",
    "PI",
    "RJ",
    "RN",
    "RS",
    "RO",
    "RR",
    "SC",
    "SP",
    "SE",
    "TO",
}


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

    # Lógica de extração da UF aprimorada e corrigida
    nome_cartorio = data.get("NomeCartorio", "")
    data["UF"] = ""  # Define um valor padrão
    if nome_cartorio:
        # Divide o nome por espaços e hífens para pegar a última palavra
        parts = nome_cartorio.replace("-", " ").split()
        if parts:
            last_part = parts[-1].strip().upper()
            # Verifica se a última parte é uma UF válida
            if last_part in UFS_BRASIL:
                data["UF"] = last_part

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

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    # options.add_argument("--headless")

    driver = None
    retry_counts = defaultdict(int)

    i = 0
    while i < len(cns_list):
        cns = cns_list[i]

        if retry_counts[cns] >= MAX_RETRIES:
            logging.critical(
                f"CNS {cns}: Excedeu o limite de {MAX_RETRIES} tentativas. Pulando permanentemente."
            )
            # REQUERIMENTO: Não fazer nada no banco, apenas pular.
            i += 1
            continue

        try:
            if driver is None:
                logging.info("Iniciando uma nova instância do navegador...")
                driver = webdriver.Chrome(options=options)

            logging.info(
                f"--- Processando {i+1}/{total}: CNS {cns} (Tentativa {retry_counts[cns] + 1}) ---"
            )
            scraped_data = scrape_cns_data(driver, cns)

            if (
                not scraped_data.get("NomeCartorio")
                or scraped_data.get("NomeCartorio") == DEFAULT_NOT_FOUND_TEXT
            ):
                raise ValueError("Extração falhou, Nome do Cartório não encontrado.")

            if update_cartorio_data(cns, scraped_data):
                i += 1  # Sucesso! Avança para o próximo CNS.
            else:
                # Se a atualização do banco falhar, trata como um erro recuperável
                raise Exception("Falha ao salvar os dados no banco de dados.")

            time.sleep(1)

        except UnexpectedAlertPresentException as e:
            # Tratamento específico para o alerta "CNS não cadastrado"
            if e.alert_text and "CNS não cadastrado" in e.alert_text:
                logging.warning(
                    f"CNS {cns}: O site informou 'CNS não cadastrado'. Pulando."
                )
                # REQUERIMENTO: Não fazer nada no banco, apenas pular.
                i += 1  # Pula para o próximo CNS, sem novas tentativas.
                try:
                    if driver:
                        driver.switch_to.alert.accept()
                except Exception:
                    pass  # Se o alerta já sumiu, ignora.
            else:
                # Se for outro tipo de alerta, usa a lógica de retry normal
                logging.error(
                    f"CNS {cns}: Alerta inesperado: {e.alert_text}. Reiniciando o driver."
                )
                retry_counts[cns] += 1
                # Limpa o estado do driver após um alerta desconhecido
                if driver:
                    driver.quit()
                driver = None
                time.sleep(2)

        except (TimeoutException, WebDriverException, ValueError) as e:
            logging.error(
                f"CNS {cns}: Falha no processamento. Causa: {e}. O navegador será reiniciado."
            )
            retry_counts[cns] += 1
            if driver:
                driver.quit()
            driver = None
            time.sleep(5)
        except Exception as e:
            logging.critical(f"CNS {cns}: Erro crítico. Causa: {e}")
            retry_counts[cns] += 1
            if driver:
                driver.quit()
            driver = None
            time.sleep(5)

    if driver:
        logging.info("--- FIM DO PROCESSAMENTO --- Fechando navegador.")
        driver.quit()
    else:
        logging.info("--- FIM DO PROCESSAMENTO ---")


if __name__ == "__main__":
    main()
