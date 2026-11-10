import sqlite3
import json
import os
from datetime import datetime, timedelta

def exportar():
    print("Lendo banco e formatando para o frontend...")
    conn = sqlite3.connect('radar.db')
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM editais")
    rows = cursor.fetchall()
    
    saida = []
    hoje = datetime.now()
    
    # Data de validade da verificação (vamos dizer que é válido por 24h)
    validade_iso = (hoje + timedelta(days=365)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    
    for e in rows:
        prazo_iso = None
        sem_data_final = True
        
        if e['prazo']:
            # Cria a data no formato exato ISO que o JavaScript entende
            prazo_iso = f"{e['prazo']}T23:59:59.999-03:00"
            sem_data_final = False
            
        item = {
            "t": e["titulo"] or "",
            "o": e["orgao"] or "",
            "tipo": e["tipo"] or "Outro",
            "est": e["estagio"] or "Qualquer",
            "v": e["valor"] or 0,
            "prazo": e["prazo"],
            "desc": e["descricao"] or "",
            "link": e["url"] or "",
            "n": 1, 
            "r": 0,
            "revisar": e["revisar"],
            "status": "aberto",
            "requisitos": e["requisitos"] or "",
            
            # As chaves exatas que o seu setData() exige:
            "validado_automaticamente": True,
            "validado_manualmente": False,
            "sem_data_final": sem_data_final,
            "prazo_iso": prazo_iso,
            "verificacao_valida_ate": validade_iso
        }
        saida.append(item)
        
    os.makedirs('docs', exist_ok=True)
    with open('docs/editais.json', 'w', encoding='utf-8') as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
        
    print(f"✅ SUCESSO! {len(saida)} editais exportados com os campos exatos do frontend.")
    conn.close()

if __name__ == "__main__":
    exportar()
