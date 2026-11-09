import sqlite3
import re
from datetime import datetime

def extrair_datas_regex(texto):
    if not texto:
        return []
    datas = []
    # Padrão 1: 15/03/2025
    for match in re.finditer(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b', texto):
        dia, mes, ano = match.groups()
        try: datas.append(datetime(int(ano), int(mes), int(dia)))
        except ValueError: pass
    # Padrão 2: 15 de março de 2025
    meses = {'janeiro':1, 'fevereiro':2, 'março':3, 'abril':4, 'maio':5, 'junho':6, 'julho':7, 'agosto':8, 'setembro':9, 'outubro':10, 'novembro':11, 'dezembro':12}
    for match in re.finditer(r'\b(\d{1,2})\s+de\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})\b', texto, re.IGNORECASE):
        dia, mes_nome, ano = match.groups()
        mes_num = meses.get(mes_nome.lower())
        if mes_num:
            try: datas.append(datetime(int(ano), int(mes_num), int(dia)))
            except ValueError: pass
    return datas

def rodar_resgate():
    print("🔍 Conectando ao banco e buscando editais para revisar...")
    try:
        conn = sqlite3.connect('radar.db')
        cursor = conn.cursor()
        
        # Busca editais que precisam de revisão OU estão sem prazo
        cursor.execute("SELECT id, descricao, requisitos, trecho_prazo FROM editais WHERE revisar = 1 OR prazo IS NULL OR prazo = ''")
        pendentes = cursor.fetchall()
        
        hoje = datetime.now()
        resgatados = 0
        
        for edital_id, desc, req, trecho in pendentes:
            # Junta todos os textos disponíveis para procurar a data
            texto_completo = f"{desc or ''} {req or ''} {trecho or ''}"
            
            datas = extrair_datas_regex(texto_completo)
            if datas:
                data_final = max(datas) # Pega a data mais no futuro
                data_formatada = data_final.strftime('%Y-%m-%d')
                
                # Atualiza a data e remove a flag de revisão
                cursor.execute("""
                    UPDATE editais 
                    SET prazo = ?, revisar = 0, atualizado_em = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (data_formatada, edital_id))
                resgatados += 1
        
        conn.commit()
        conn.close()
        print(f"🎉 Resgate concluído! {resgatados} editais foram atualizados e liberados para exportação.")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    rodar_resgate()
