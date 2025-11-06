import sys
from db import get_db_connection


def create_cartorios_table():
    """
    Cria a tabela 'cartorios_enriquecidos' no banco de dados se ela não existir.
    """
    conn = None  # Inicializa a conexão como None
    try:
        conn = get_db_connection()
        if not conn:
            print("Falha ao obter conexão com o banco. Abortando a criação da tabela.")
            sys.exit(1)  # Encerra o script com código de erro

        cursor = conn.cursor()

        table_name = "cartorios_enriquecidos"

        # SQL para criar a tabela. CNS é a chave primária.
        create_table_sql = f"""
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{table_name}' and xtype='U')
        CREATE TABLE {table_name} (
            CNS VARCHAR(20) PRIMARY KEY,
            NomeCartorio NVARCHAR(255),
            UF CHAR(2),
            Tabeliao NVARCHAR(255),
            Endereco NVARCHAR(MAX),
            CEP VARCHAR(10),
            Telefone VARCHAR(100),
            Email NVARCHAR(255),
            Site NVARCHAR(255),
            Atribuicoes NVARCHAR(MAX),
            data_extracao DATETIME DEFAULT GETDATE()
        );
        """

        print(f"Verificando/Criando a tabela '{table_name}'...")
        cursor.execute(create_table_sql)
        conn.commit()
        print(f"Tabela '{table_name}' pronta para uso.")

    except Exception as e:
        print(f"Erro ao criar a tabela: {e}")
        # Se houver um erro, é importante não deixar a transação aberta
        if conn:
            conn.rollback()
    finally:
        if "cursor" in locals():
            cursor = locals().get("cursor")
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print("Conexão com o banco de dados fechada.")


if __name__ == "__main__":
    create_cartorios_table()
