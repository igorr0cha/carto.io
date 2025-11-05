import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

# Pega as credenciais do banco de dados do ambiente
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# Valida se todas as variáveis necessárias foram definidas
required_vars = {
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_NAME": DB_NAME,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
}
missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    raise ValueError(
        f"Variáveis de ambiente não definidas no .env: {', '.join(missing_vars)}"
    )

# --- Monta a string de conexão ---
# NOTA: O driver ODBC pode variar dependendo da sua instalação.
# 'ODBC Driver 17 for SQL Server' é comum, mas pode ser necessário ajustá-lo.
CONN_STRING = (
    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
    f"SERVER={DB_HOST},{DB_PORT};"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};"
    f"PWD={DB_PASSWORD};"
)

print("Conexão com o banco de dados montada com sucesso!")
