import sqlite3

def limpar():
    conn = sqlite3.connect('radar.db')
    cursor = conn.cursor()
    # Deleta qualquer edital que tenha 2022, 2023 ou 2024 no título ou link
    query = """
        DELETE FROM editais 
        WHERE titulo LIKE '%2022%' OR url LIKE '%2022%'
           OR titulo LIKE '%2023%' OR url LIKE '%2023%'
           OR titulo LIKE '%2024%' OR url LIKE '%2024%'
    """
    cursor.execute(query)
    deletados = cursor.rowcount
    conn.commit()
    conn.close()
    print(f"✅ Limpeza concluída! {deletados} editais antigos foram deletados.")

if __name__ == "__main__":
    limpar()
