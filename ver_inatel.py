import sqlite3

def ver_inatel():
    conn = sqlite3.connect('radar.db')
    cursor = conn.cursor()
    cursor.execute("SELECT titulo, prazo, revisar, descricao, requisitos, trecho_prazo FROM editais WHERE titulo LIKE '%INATEL%' OR url LIKE '%INATEL%' OR url LIKE '%inatel%'")
    resultados = cursor.fetchall()
    
    if not resultados:
        print("❌ O edital do INATEL não está no banco de dados.")
    else:
        for r in resultados:
            print(f"Título: {r[0]}")
            print(f"Prazo: {r[1]}")
            print(f"Revisar: {r[2]}")
            print(f"Trecho do Prazo: {r[5]}")
            print(f"Descrição: {r[3][:150]}...")
            print("-" * 30)
            
    conn.close()

if __name__ == "__main__":
    ver_inatel()
