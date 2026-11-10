import sqlite3
import subprocess

def matar_natura():
    print("🔍 Procurando o edital da Natura no banco...")
    conn = sqlite3.connect('radar.db')
    cursor = conn.cursor()
    
    # Busca por qualquer menção à Natura no título ou descrição
    cursor.execute("DELETE FROM editais WHERE titulo LIKE '%Natura%' OR descricao LIKE '%Natura%'")
    deletados = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✅ {deletados} edital(is) da Natura foram deletados do banco.")
    
    print("🔄 Rodando o exportador novamente...")
    subprocess.run(["python", "exportar_manual.py"])

if __name__ == "__main__":
    matar_natura()
