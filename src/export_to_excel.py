import pandas as pd
import sys
import os
from db import get_db_connection

# --- Configurações ---
TABLE_NAME = "cartorios_enriquecidos"
OUTPUT_FOLDER = "data_output"
OUTPUT_FILENAME = "resultado_cartorios_enriquecidos.xlsx"


def main():
    """
    Exporta todos os dados da tabela 'cartorios_enriquecidos' para um arquivo Excel.
    """
    print("Iniciando processo de exportação...")

    conn = get_db_connection()
    if not conn:
        print("Não foi possível conectar ao banco de dados. Abortando.")
        sys.exit(1)

    try:
        # A consulta SQL para selecionar todos os dados da tabela.
        sql_query = f"SELECT * FROM {TABLE_NAME}"
        print(f"Executando consulta na tabela '{TABLE_NAME}'...")

        # O pandas.read_sql é a forma mais eficiente de carregar dados de uma query.
        df = pd.read_sql(sql_query, conn)

        print(f"Foram encontrados {len(df)} registros no banco de dados.")

        if df.empty:
            print("A tabela está vazia. Nenhum arquivo será gerado.")
            return

        # Garante que a pasta de saída exista.
        # O '..' sobe um nível do diretório 'src' para encontrar 'data_output'.
        output_dir_path = os.path.join(os.path.dirname(__file__), "..", OUTPUT_FOLDER)
        if not os.path.exists(output_dir_path):
            os.makedirs(output_dir_path)
            print(f"Pasta de saída criada em: {output_dir_path}")

        output_file_path = os.path.join(output_dir_path, OUTPUT_FILENAME)

        # Exporta o DataFrame para um arquivo Excel.
        # index=False evita que o índice do pandas seja escrito no arquivo.
        df.to_excel(output_file_path, index=False, engine="openpyxl")

        print("-" * 50)
        print(">>> EXPORTAÇÃO CONCLUÍDA COM SUCESSO! <<<")
        print(f"Arquivo salvo em: {output_file_path}")
        print("-" * 50)

    except Exception as e:
        print(f"Ocorreu um erro durante a exportação: {e}")
    finally:
        if conn:
            conn.close()
            print("Conexão com o banco de dados fechada.")


if __name__ == "__main__":
    main()
