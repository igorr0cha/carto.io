import pyodbc
from settings import CONN_STRING  # Importa a string de conexão


def get_db_connection():
    """
    Cria e retorna uma conexão com o banco de dados SQL Server.
    """
    try:
        conn = pyodbc.connect(CONN_STRING)
        return conn
    except Exception as e:
        print(f"Erro CRÍTICO ao conectar no SQL Server: {e}")
        print(
            "Verifique a string de conexão no .env e se o driver ODBC está instalado."
        )
        return None


# --- Bloco de Teste ---
# Este código só roda quando você executa `python src/db.py` diretamente
if __name__ == "__main__":
    print("Testando conexão com o SQL Server...")

    conn = get_db_connection()

    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            resultado = cursor.fetchone()
            if resultado is not None and len(resultado) > 0:
                print(f"Resultado do SELECT 1: {resultado[0]}")
            else:
                print("Resultado do SELECT 1: retornou None")
            print(">>> Conexão bem-sucedida! <<<")

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Erro ao executar 'SELECT 1': {e}")
