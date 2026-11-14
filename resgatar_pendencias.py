import sqlite3
import re
from datetime import datetime

MESES = {
    'janeiro': 1, 'jan': 1,
    'fevereiro': 2, 'fev': 2,
    'março': 3, 'marco': 3, 'mar': 3,
    'abril': 4, 'abr': 4,
    'maio': 5, 'mai': 5,
    'junho': 6, 'jun': 6,
    'julho': 7, 'jul': 7,
    'agosto': 8, 'ago': 8,
    'setembro': 9, 'set': 9,
    'outubro': 10, 'out': 10,
    'novembro': 11, 'nov': 11,
    'dezembro': 12, 'dez': 12
}

REGEX_MESES = '|'.join(sorted(MESES.keys(), key=len, reverse=True))


def inferir_ano(texto_contexto, ano_padrao):
    m = re.search(r'\b(202[4-9])\b', texto_contexto or '')
    return int(m.group(1)) if m else ano_padrao


def extrair_datas_regex(trecho, texto_apoio="", ano_padrao=None):
    if not trecho:
        return []
    if ano_padrao is None:
        ano_padrao = datetime.now().year
    datas = []
    ano_inferido = inferir_ano(f"{trecho} {texto_apoio}", ano_padrao)

    # Padrão 1: 15/03/2026 ou 15/03/26
    for match in re.finditer(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})\b', trecho):
        dia, mes, ano = match.groups()
        ano_int = int(ano) + 2000 if len(ano) == 2 else int(ano)
        try:
            datas.append(datetime(ano_int, int(mes), int(dia)))
        except ValueError:
            pass

    # Padrão 2: 15 de março de 2026 ou 09 de dez. de 2026
    padrao_extenso_ano = rf'\b(\d{{1,2}})[º°]?\s+(?:de\s+)?({REGEX_MESES})\.?\s+(?:de\s+)?(\d{{4}})\b'
    for match in re.finditer(padrao_extenso_ano, trecho, re.IGNORECASE):
        dia, mes_nome, ano = match.groups()
        mes_num = MESES.get(mes_nome.lower().rstrip('.'))
        if mes_num:
            try:
                datas.append(datetime(int(ano), int(mes_num), int(dia)))
            except ValueError:
                pass

    if datas:
        return datas

    # Padrão 3 (sem ano explícito na data): "até 30 de novembro" ou "de 5 de novembro a 13 de dezembro"
    padrao_extenso_sem_ano = rf'\b(\d{{1,2}})[º°]?\s+de\s+({REGEX_MESES})\.?\b'
    for match in re.finditer(padrao_extenso_sem_ano, trecho, re.IGNORECASE):
        dia, mes_nome = match.groups()
        mes_num = MESES.get(mes_nome.lower().rstrip('.'))
        if mes_num:
            try:
                datas.append(datetime(ano_inferido, int(mes_num), int(dia)))
            except ValueError:
                pass

    # Padrão 4 (curto sem ano em contexto de inscrição): "de 13/4 a 22/5"
    if re.search(r'inscri[cç]|submiss|prazo|at[eé]', trecho, re.IGNORECASE):
        for match in re.finditer(r'\b(\d{1,2})/(\d{1,2})\b', trecho):
            dia, mes = match.groups()
            try:
                datas.append(datetime(ano_inferido, int(mes), int(dia)))
            except ValueError:
                pass

    return datas


def rodar_resgate():
    print("🔍 Conectando ao banco e buscando editais para revisar...")
    try:
        conn = sqlite3.connect('radar.db')
        cursor = conn.cursor()

        # Busca editais que precisam de revisão OU estão sem prazo
        cursor.execute("SELECT id, titulo, descricao, requisitos, trecho_prazo FROM editais WHERE revisar = 1 OR prazo IS NULL OR prazo = ''")
        pendentes = cursor.fetchall()

        resgatados = 0

        for edital_id, titulo, desc, req, trecho in pendentes:
            # Extrai datas exclusivamente do trecho_prazo para evitar falsos positivos de descrição/requisitos
            datas = extrair_datas_regex(trecho, texto_apoio=f"{titulo or ''} {desc or ''}")
            if datas:
                data_final = max(datas)  # Pega a data de encerramento do período de inscrição
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
        print(f"🎉 Resgate concluído! {resgatados} editais foram atualizados com prazo extraído de trecho_prazo.")
    except Exception as e:
        print(f"❌ Erro: {e}")


if __name__ == "__main__":
    rodar_resgate()
