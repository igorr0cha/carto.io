import pandas as pd
import sys
from db import get_db_connection

# --- Configurações ---
EXCEL_PATH = "data_input/base_cartorios_com_cns.xlsx"
# IMPORTANTE: Ajuste este nome se a coluna no seu Excel for diferente.
CNS_COLUMN_NAME = "CNS"
TABLE_NAME = "cartorios_enriquecidos"


def load_cns_from_excel(file_path, column_name):
    """Lê a coluna de CNS do arquivo Excel e retorna uma lista limpa."""
    try:
        df = pd.read_excel(file_path, dtype={column_name: str})
        # Garante que não há valores nulos e remove espaços em branco
        cns_list = df[column_name].dropna().str.strip().tolist()
        print(f"Encontrados {len(cns_list)} CNS no arquivo Excel.")
        return cns_list
    except FileNotFoundError:
        print(f"ERRO: Arquivo Excel não encontrado em '{file_path}'")
        sys.exit(1)
    except KeyError:
        print(f"ERRO: A coluna '{column_name}' não foi encontrada no arquivo Excel.")
        sys.exit(1)


def get_existing_cns(cursor):
    """Busca no banco de dados todos os CNS já inseridos e retorna um set."""
    cursor.execute(f"SELECT CNS FROM {TABLE_NAME}")
    # Usar um 'set' para buscas O(1), muito mais rápido que uma lista.
    return {row.CNS for row in cursor.fetchall()}


def main():
    """Função principal para popular o banco com CNS do Excel."""
    all_cns_from_excel = load_cns_from_excel(EXCEL_PATH, CNS_COLUMN_NAME)

    if not all_cns_from_excel:
        print("Nenhum CNS para processar. Encerrando.")
        return

    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            sys.exit(1)

        cursor = conn.cursor()

        existing_cns = get_existing_cns(cursor)
        print(f"Encontrados {len(existing_cns)} CNS já existentes no banco de dados.")

        # Filtra para inserir apenas os CNS que ainda não estão no banco.
        cns_to_insert = [cns for cns in all_cns_from_excel if cns not in existing_cns]

        if not cns_to_insert:
            print(
                "Todos os CNS do Excel já estão no banco de dados. Nenhuma ação necessária."
            )
            return

        print(f"Inserindo {len(cns_to_insert)} novos CNS no banco de dados...")

        # Prepara os dados para inserção em lote
        sql_insert = f"INSERT INTO {TABLE_NAME} (CNS) VALUES (?)"
        data_to_insert = [(cns,) for cns in cns_to_insert]

        # executemany é muito mais eficiente para múltiplas inserções.
        cursor.executemany(sql_insert, data_to_insert)
        conn.commit()

        print(f"Sucesso! {cursor.rowcount} novos CNS foram inseridos.")

    except Exception as e:
        print(f"Ocorreu um erro durante a inserção no banco: {e}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
        print("Processo finalizado. Conexão com o banco fechada.")


if __name__ == "__main__":
    main()
