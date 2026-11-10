import sqlite3
import subprocess

def limpar():
    print("🧹 Limpando editais de 2024 (incluindo Natura) do banco...")
    conn = sqlite3.connect('radar.db')
    cursor = conn.cursor()
    
    # Deleta qualquer edital com 2024 no título ou URL
    query = "DELETE FROM editais WHERE titulo LIKE '%2024%' OR url LIKE '%2024%' OR descricao LIKE '%2024%'"
    cursor.execute(query)
    deletados = cursor.rowcount
    conn.commit()
    conn.close()
    
    print(f"✅ {deletados} editais de 2024 deletados do banco.")
    
    # Roda o exportador automaticamente
    print("🔄 Rodando o exportador...")
    subprocess.run(["python", "exportar_manual.py"])

if __name__ == "__main__":
    limpar()
