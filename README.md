# Projeto de Automação e Enriquecimento de Cartórios (CNS Scraper)

Este projeto contém um robô de automação (RPA/Scraping) desenvolvido em Python para consultar e enriquecer uma base de dados de cartórios brasileiros, utilizando o código CNS (Cadastro Nacional de Serventias) como chave de busca.

O robô foi construído com foco em **Resiliência**, **Idempotência** e **Manutenibilidade**, utilizando um banco de dados SQL Server como gerenciador de estado para criar uma fila de processamento robusta e à prova de falhas.

## 🏛️ Visão Geral da Arquitetura (Lógica de Fila de Trabalho)

Em vez de simplesmente ler um CSV e processá-lo em memória (o que é arriscado), este projeto utiliza uma arquitetura de **Fila de Trabalho (Job Queue)** diretamente no banco de dados.

O fluxo é dividido em quatro etapas distintas:

1.  **Setup do Banco (`src/create_table.py`):** Um script de execução única que cria a tabela de destino (`dbo.CartoriosConsulta`) no SQL Server. Esta tabela armazena não apenas os dados finais, mas também o **status** do processamento.

2.  **População da Fila (`src/populate_cns.py`):** Este script lê o arquivo CSV de entrada (`data_input/*.csv`), extrai a lista de CNS e os insere na tabela `dbo.CartoriosConsulta` com um status inicial (ex: "PENDENTE"). Isso transforma o banco de dados em nossa lista de tarefas.

3.  **Processamento do Scraper (`src/main_scraper.py`):** Este é o robô principal. Ele opera em um loop contínuo:
    * Ele consulta o banco por todos os CNS com status "PENDENTE".
    * Para cada um, ele tenta executar o scraping no site-alvo.
    * **Se falhar:** Ele atualiza o status no banco para "ERRO" (junto com a mensagem de erro) e continua para o próximo.
    * **Se for bem-sucedido:** Ele preenche todos os dados coletados (Nome, Endereço, etc.) e atualiza o status para "CONCLUIDO".

4.  **Exportação (`src/export_to_excel.py`):** Um script final que consulta o banco por todos os registros "CONCLUIDO" e gera o arquivo Excel (`.xlsx`) solicitado na pasta `data_output/`.

### Vantagens desta Arquitetura (SRE)

* **Resiliência Total:** Se o robô (`main_scraper.py`) parar por qualquer motivo (queda de rede, bloqueio de IP, `Ctrl+C`), basta executá-lo novamente. Ele simplesmente buscará os próximos itens "PENDENTE" no banco, retomando o trabalho exatamente de onde parou.
* **Observabilidade:** É fácil auditar o processo. Uma consulta SQL (`SELECT Status, COUNT(*) FROM dbo.CartoriosConsulta GROUP BY Status`) mostra exatamente o que foi feito, o que falhou e o que falta.
* **Paralelismo (Escala Futura):** Esta arquitetura permite, no futuro, rodar múltiplos instâncias do `main_scraper.py` em paralelo. O banco de dados garantirá (com `SELECT...WITH (UPDLOCK, READPAST)`) que diferentes robôs não peguem o mesmo item "PENDENTE".

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python 3.10+
* **Banco de Dados:** Microsoft SQL Server
* **Conexão DB:** `pyodbc`
* **Manipulação de Dados:** `pandas` (para leitura do CSV e exportação do Excel)
* **RPA/Scraping:** [Playwright / Selenium] *(Adicione a ferramenta que você está usando)*
* **Gerenciamento de Segredos:** `python-dotenv`

---

## 📂 Estrutura de Pastas
```
/carto.io/
├── .venv/ # Ambiente virtual Python
├── data_input/
│ └── base_cartorios_com_cns.xlsx - cns.csv
├── data_output/
│ └── (vazio, aqui serão gerados os relatórios .xlsx)
├── logs/
│ └── erros_scraping.log # Log de falhas
├── src/
│ ├── init.py
│ ├── settings.py # Carrega variáveis de ambiente (conexão DB)
│ ├── db.py # Funções utilitárias de conexão com o banco
│ ├── create_table.py # PASSO 1: Cria a tabela de destino
│ ├── populate_cns.py # PASSO 2: Lê o CSV e popula a fila no DB
│ ├── main_scraper.py # PASSO 3: O robô principal que processa a fila
│ └── export_to_excel.py # PASSO 4: Gera o Excel final
├── .env # Arquivo de configuração (NÃO VERSIONADO)
├── .gitignore
├── requirements.txt # Dependências do projeto
└── README.md # Esta documentação
```


---

## 🚀 Guia de Instalação e Execução

Siga estes passos para configurar e rodar o projeto.

### 1. Pré-requisitos

* Python 3.10 ou superior.
* Acesso a um banco de dados SQL Server (local ou remoto).
* Driver Microsoft ODBC para SQL Server instalado na máquina.

### 2. Instalação

1.  Clone este repositório:
    ```bash
    git clone [URL_DO_SEU_REPOSITORIO]
    cd carto.io
    ```

2.  Crie e ative um ambiente virtual:
    ```bash
    # Windows
    python -m venv .venv
    .\.venv\Scripts\activate
    
    # macOS / Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  Instale as dependências:
    ```bash
    pip install -r requirements.txt
    ```

4.  Configure suas credenciais:
    * Crie um arquivo chamado `.env` na raiz do projeto.
    * Adicione sua string de conexão do SQL Server dentro dele:
    ```ini
    # Arquivo: .env
    SQL_SERVER_CONN_STRING="DRIVER={ODBC Driver 17 for SQL Server};SERVER=SEU_SERVIDOR;DATABASE=SEU_BANCO_DE_TESTE;UID=SEU_USUARIO;PWD=SUA_SENHA"
    ```
    *(**Importante:** O `.env` está no `.gitignore` e nunca deve ser enviado para o repositório).*

### 3. Como Executar (Fluxo de Trabalho)

O projeto é executado em 4 passos sequenciais:

#### Passo 1: Criar a Tabela (Execução Única)
Este script cria a tabela `dbo.CartoriosConsulta` no seu banco de dados.
```bash
python src/create_table.py
```

Verifique seu banco de dados (SSMS) para confirmar que a tabela foi criada.

#### Passo 2: Popular a Fila de Trabalho (Execução Única)
Este script lê o arquivo data_input/base_cartorios_com_cns.xlsx - cns.csv e insere todos os CNS na tabela com o status "PENDENTE".

```bash
python src/populate_cns.py
```
Execute um SELECT COUNT(*) na tabela para confirmar que os ~2.800 registros foram inseridos.

#### Passo 3: Executar o Robô de Scraping
Este é o script principal. Ele irá rodar indefinidamente (ou até que todos os itens "PENDENTE" sejam processados), consultando o site e atualizando o banco.

```bash
python src/main_scraper.py
```
Você pode parar este script (Ctrl+C) a qualquer momento. Para retomar, basta executá-lo novamente.

#### Passo 4: Gerar o Relatório Final
Após o main_scraper.py concluir (ou quando você desejar um relatório parcial), execute este script.

```bash
python src/export_to_excel.py
```

---

# ⚠️ Observações Importantes:
Substitua [URL_DO_SEU_REPOSITORIO], SEU_SERVIDOR, SEU_BANCO_DE_TESTE, SEU_USUARIO e SUA_SENHA pelos valores reais do seu ambiente.
Certifique-se de que o arquivo de entrada em data_input/ está no formato correto (CSV com coluna CNS).
O scraper está configurado para respeitar os termos de uso do site-alvo. Adicione delays ou proxies conforme necessário para evitar bloqueios.
Os logs de erro são salvos em logs/erros_scraping.log para facilitar a análise de falhas.

---

# 📄 Licença
Este projeto é de uso interno e não possui licença pública. Todos os direitos reservados.
```
