import sqlite3

def achar():
    conn = sqlite3.connect('radar.db')
    cursor = conn.cursor()
    # Busca por 'Baita' no título ou descrição
    cursor.execute("SELECT id, titulo, prazo, descricao FROM editais WHERE titulo LIKE '%Baita%' OR descricao LIKE '%Baita%'")
    resultados = cursor.fetchall()
    
    if not resultados:
        print("Nenhum edital da Baita encontrado no banco (pode já ter sido deletado).")
    else:
        for r in resultados:
            print(f"ID: {r[0]}")
            print(f"Título: {r[1]}")
            print(f"Prazo: {r[2]}")
            print(f"Descrição: {r[3][:100]}...\n")
            
    conn.close()

if __name__ == "__main__":
    achar()
