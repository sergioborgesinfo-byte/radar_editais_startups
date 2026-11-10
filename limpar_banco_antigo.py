import sqlite3

def limpar_antigos():
    print("🧹 Procurando editais antigos (2022, 2023, 2024) no banco...")
    try:
        conn = sqlite3.connect('radar.db')
        cursor = conn.cursor()
        
        # Deleta qualquer edital que tenha o ano antigo no título ou na URL
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
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    limpar_antigos()
