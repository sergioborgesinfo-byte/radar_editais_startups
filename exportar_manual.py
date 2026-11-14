import sqlite3
import json
import os
import re
from datetime import datetime, timedelta


def normalizar(s):
    return re.sub(r'\W+', ' ', (s or '').lower()).strip()


def palavras_chave(s):
    ignorar = {'edital', 'chamada', 'publica', 'programa', 'para', 'startups', 'startup', 'selecao', 'inovacao', 'aberta', 'processo', 'seletivo', 'fluxo', 'continuo', 'rodada', 'edicao', 'ciclo'}
    return {p for p in normalizar(s).split() if len(p) > 2 and p not in ignorar}


def eh_fluxo_continuo(e, titulos_vencidos):
    # 1. Páginas de anexo ou homepages genéricas sem caminho específico não comprovam edital aberto
    url = (e.get('url') or '').lower()
    if re.search(r'anexo\d*\.pdf|/default\.aspx$', url):
        return False

    # 2. Se o próprio programa já possui o edital específico com prazo vencido no banco, a landing page não está aberta
    palavras_e = palavras_chave(e.get('titulo'))
    for tv in titulos_vencidos:
        if palavras_e and tv and len(palavras_e & tv) / min(len(palavras_e), len(tv)) >= 0.75:
            return False

    # 3. Se tiver verificação automática, exige que sem_data_final seja 1 E tenha frase explícita de abertura contínua
    trecho_ab = (e.get("v_trecho_abertura") or "").lower()
    texto_completo = f"{e.get('titulo','')} {e.get('descricao','')} {trecho_ab}".lower()

    if e.get("v_sem_data_final") == 0:
        # Foi verificado pelo radar_automacao e reprovado como fluxo contínuo (ex: anexo sem data ou regulamento condicional)
        if not re.search(r"inscri[cç][oõ]es permanecer[aã]o abertas em fluxo cont[ií]nuo|chamada prospectiva cont[ií]nua", texto_completo):
            return False

    return bool(re.search(r"fluxo cont[ií]nuo|inscri[cç][oõ]es cont[ií]nuas|chamada prospectiva cont[ií]nua", texto_completo))


def ano_antigo_detectado(e, ano_atual=None, titulos_vencidos=()):
    if ano_atual is None:
        ano_atual = datetime.now().year
    texto_completo = f"{e.get('titulo','')} {e.get('url','')} {e.get('descricao','')} {e.get('requisitos','')} {e.get('trecho_prazo','')}".lower()

    # 1. Se for fluxo contínuo, NUNCA é fantasma (mesmo se citado ano anterior)
    if eh_fluxo_continuo(e, titulos_vencidos):
        return False

    # 2. Se tiver menção a anos anteriores ao atual, é fantasma
    anos_antigos = [str(a) for a in range(2020, ano_atual)]
    for ano in anos_antigos:
        if ano in texto_completo:
            return True
    return False


def eh_duplicado(novo, existentes):
    novo_t = normalizar(novo.get('t'))
    novo_o = normalizar(novo.get('o'))
    novo_p = novo.get('prazo') or 'continuo'
    palavras_novo = {p for p in novo_t.split() if len(p) > 2}

    for ex in existentes:
        if novo.get('link') and novo.get('link') == ex.get('link'):
            return True
        ex_p = ex.get('prazo') or 'continuo'
        if novo_p != ex_p:
            continue
        ex_t = normalizar(ex.get('t'))
        ex_o = normalizar(ex.get('o'))
        if novo_t == ex_t and novo_o == ex_o:
            return True
        # Mesmo prazo e alta sobreposição de termos do título (ex: BNDES Garagem / HubMG GOV)
        palavras_ex = {p for p in ex_t.split() if len(p) > 2}
        if palavras_novo and palavras_ex:
            intersecao = palavras_novo & palavras_ex
            menor = min(len(palavras_novo), len(palavras_ex))
            if menor >= 2 and len(intersecao) / menor >= 0.75:
                return True
    return False


def exportar():
    print("Lendo banco e formatando para o frontend...")
    conn = sqlite3.connect('radar.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT e.*, v.sem_data_final AS v_sem_data_final, v.trecho_abertura AS v_trecho_abertura
            FROM editais e
            LEFT JOIN verificacoes_automaticas v ON v.edital_id = e.id
            ORDER BY e.valor DESC, length(e.url) ASC
        """)
    except sqlite3.OperationalError:
        cursor.execute("SELECT * FROM editais ORDER BY valor DESC")

    rows = cursor.fetchall()

    saida = []
    hoje = datetime.now()
    hoje_str = hoje.strftime('%Y-%m-%d')

    # Mapeia títulos de editais que já têm prazo vencido comprovado no banco
    titulos_vencidos = [
        palavras_chave(r['titulo'])
        for r in rows
        if r['prazo'] and r['prazo'] < hoje_str
    ]

    # Validade da verificação para o frontend (renovada a cada execução do robô)
    validade_iso = (hoje + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M:%S.000Z')

    ignorados_vencidos = 0
    ignorados_sem_prazo = 0
    ignorados_duplicados = 0

    for row in rows:
        e = dict(row)
        if ano_antigo_detectado(e, hoje.year, titulos_vencidos):
            continue

        prazo = e.get('prazo')
        continuo = eh_fluxo_continuo(e, titulos_vencidos)

        if prazo:
            # Ignora editais cujo prazo de inscrição já passou
            if prazo < hoje_str:
                ignorados_vencidos += 1
                continue
            prazo_iso = f"{prazo}T23:59:59.999-03:00"
            sem_data_final = False
            revisar = 0
            dias = (datetime.strptime(prazo, "%Y-%m-%d").date() - hoje.date()).days
        elif continuo:
            prazo_iso = None
            sem_data_final = True
            revisar = 0
            dias = None
        else:
            # Sem prazo identificado e não é fluxo contínuo comprovado
            ignorados_sem_prazo += 1
            continue

        item = {
            "t": e["titulo"] or "",
            "o": e["orgao"] or "",
            "tipo": e["tipo"] or "Outro",
            "est": e["estagio"] or "Qualquer",
            "v": e["valor"] or 0,
            "prazo": prazo,
            "d": dias,
            "desc": e["descricao"] or "",
            "link": e["url"] or "",
            "n": 1,
            "r": 0,
            "revisar": revisar,
            "status": "inscricoes_abertas" if sem_data_final else "aberto",
            "requisitos": e["requisitos"] or "",
            "validado_automaticamente": True,
            "validado_manualmente": False,
            "sem_data_final": sem_data_final,
            "prazo_iso": prazo_iso,
            "verificacao_valida_ate": validade_iso
        }

        if eh_duplicado(item, saida):
            ignorados_duplicados += 1
            continue

        saida.append(item)

    os.makedirs('docs', exist_ok=True)
    with open('docs/editais.json', 'w', encoding='utf-8') as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)

    print(f"✅ SUCESSO! {len(saida)} editais vigentes exportados (ignorados: {ignorados_vencidos} vencidos, {ignorados_sem_prazo} sem prazo, {ignorados_duplicados} duplicados).")
    conn.close()


if __name__ == "__main__":
    exportar()
