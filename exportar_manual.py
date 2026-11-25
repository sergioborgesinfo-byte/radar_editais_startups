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
    chaves_novo = palavras_chave(novo.get('t'))
    codigos_novo = set(re.findall(r'\b0?\d{1,3}\s+202\d\b', novo_t))

    for ex in existentes:
        if novo.get('link') and novo.get('link') == ex.get('link'):
            return True
        ex_t = normalizar(ex.get('t'))
        ex_o = normalizar(ex.get('o'))
        ex_p = ex.get('prazo') or 'continuo'
        if novo_t == ex_t and (novo_o == ex_o or novo_p == ex_p):
            return True

        # Mesmo código de chamada (ex: 018/2026) ou alta sobreposição de palavras-chave do título (mesmo com datas de etapas diferentes)
        codigos_ex = set(re.findall(r'\b0?\d{1,3}\s+202\d\b', ex_t))
        chaves_ex = palavras_chave(ex.get('t'))
        if codigos_novo and codigos_ex and (codigos_novo & codigos_ex):
            if (chaves_novo & chaves_ex):
                return True
        if chaves_novo and chaves_ex:
            inter_chaves = chaves_novo & chaves_ex
            menor_chaves = min(len(chaves_novo), len(chaves_ex))
            if menor_chaves >= 2 and len(inter_chaves) / menor_chaves >= 0.75:
                return True

        # Mesmo prazo e sobreposição geral do título
        if novo_p == ex_p:
            palavras_ex = {p for p in ex_t.split() if len(p) > 2}
            if palavras_novo and palavras_ex:
                intersecao = palavras_novo & palavras_ex
                menor = min(len(palavras_novo), len(palavras_ex))
                if menor >= 2 and len(intersecao) / menor >= 0.75:
                    return True
    return False


MAPA_UFS = [
    ("AC", r"\bacre\b|fapac"),
    ("AL", r"\balagoas\b|fapeal"),
    ("AM", r"\bamazonas\b|fapeam|\bmanaus\b"),
    ("AP", r"\bamap[aá]\b|fapeap"),
    ("BA", r"\bbahia\b|fapesb"),
    ("CE", r"\bcear[aá]\b|funcap"),
    ("DF", r"\bdistrito federal\b|fapdf|\bbras[ií]lia\b|\bride\b"),
    ("ES", r"\besp[ií]rito santo\b|fapes\b|\bserra\b|inovaserra|seedes"),
    ("GO", r"\bgoi[aá]s\b|fapeg|hubgoias"),
    ("MA", r"\bmaranh[aã]o\b|fapema"),
    ("MG", r"\bminas gerais\b|\bmineir[ao]s?\b|fapemig|hubmg|puc minas|puctec|bh\b|belo horizonte"),
    ("MS", r"\bmato grosso do sul\b|fundect"),
    ("MT", r"\bmato grosso\b(?! do sul)|fapemat"),
    ("PA", r"\bestado do par[aá]\b|\bno par[aá]\b|fapespa|\bbel[eé]m\b"),
    ("PB", r"\bpara[ií]ba\b|fapesq"),
    ("PE", r"\bpernambuco\b|facepe|porto digital"),
    ("PI", r"\bpiau[ií]\b|fapepi"),
    ("PR", r"\bparan[aá]\b|funda[cç][aã]o arauc[aá]ria|fara\.pr"),
    ("RJ", r"\brio de janeiro\b|\bcariocas?\b|faperj|invest\.rio|maravalley|startup rio"),
    ("RN", r"\brio grande do norte\b|fapern|ifrn"),
    ("RO", r"\brond[oô]nia\b|fapero"),
    ("RR", r"\broraima\b|faperr|ifrr"),
    ("RS", r"\brio grande do sul\b|\bga[uú]ch[ao]s?\b|fapergs|tecnosinos|tecnopuc"),
    ("SC", r"\bsanta catarina\b|\bcatarinense\b|fapesc|acate"),
    ("SE", r"\bsergipe\b|fapitec"),
    ("SP", r"\bs[aã]o paulo\b|\bpaulistas?\b|fapesp"),
    ("TO", r"\btocantins\b|fapt"),
]

AMAZONIA_LEGAL = ["AC", "AM", "AP", "MA", "MT", "PA", "RO", "RR", "TO"]


def extrair_metadados_match(e):
    texto = f"{e.get('titulo','')} {e.get('orgao','')} {e.get('descricao','')} {e.get('requisitos','')} {e.get('url','')}".lower()
    req = f"{e.get('requisitos','')} {e.get('descricao','')}".lower()

    # 1. Abrangência geográfica (UFs elegíveis)
    ufs = []
    if re.search(r"amaz[oô]nia legal|\bamazonia\b|bioneg[oó]cios da amaz[oô]nia|\bcba\b", texto):
        ufs.extend(AMAZONIA_LEGAL)

    nacional_explicito = bool(re.search(r"todo o pa[ií]s|todo o brasil|qualquer estado|qualquer pa[ií]s|territ[oó]rio nacional|[aâ]mbito nacional", req))
    if not nacional_explicito:
        for uf, padrao in MAPA_UFS:
            if re.search(padrao, texto) and uf not in ufs:
                ufs.append(uf)

    if not ufs or nacional_explicito:
        ufs = ["NACIONAL"]

    # 2. Exigência de CNPJ vs Aceita Pessoa Física / Ideação sem CNPJ
    aceita_pf = bool(re.search(r"pessoas? f[ií]sicas?|sem cnpj|estudantes|pesquisadores|inventores|diploma de gradua|qualquer interessado|empreendedores", req))
    exige_cnpj = bool(re.search(r"cnpj ativo|empresas brasileiras|sede ou filial|inscri[cç][aã]o no cnpj|pessoas? jur[ií]dicas?|faturamento|cooperativas", req)) and not bool(re.search(r"inclusive sem cnpj|pessoas? f[ií]sicas? e jur[ií]dicas?|com ou sem cnpj", req))

    # 3. Setores / Verticais de atuação
    setores = []
    mapa_setores = {
        "ia_deeptech": r"intelig[eê]ncia artificial|\bia\b|\bai\b|deep\s*tech|vibe coding|cient[ií]fic|biotecnologia|hardware",
        "govtech": r"govtech|setor p[uú]blico|desafios p[uú]blicos|inova[cç][aã]o p[uú]blica|governo|prefeitura|sicar|\bcar\b|bem p[uú]blico digital",
        "agritech_bio": r"agritech|agro|bioeconomia|bioneg[oó]cios|biodiversidade|rural|alimentos|foodtech|florestal",
        "healthtech": r"healthtech|sa[uú]de|m[eé]dic|hospital|biominas|f[aá]rmaco",
        "impacto_esg": r"impacto socioambiental|impacto social|sustent[aá]vel|sustentabilidade|economia solid[aá]ria|ambiental|clim[aá]tic|esg",
    }
    for chave_setor, padrao in mapa_setores.items():
        if re.search(padrao, texto):
            setores.append(chave_setor)
    if not setores:
        setores.append("geral")

    # 4. Perfis especiais e qualificações exigidas ou priorizadas nos editais
    perfis = []
    if re.search(r"mulheres|feminina|empreendedoras", texto):
        perfis.append("mulheres")
    if re.search(r"\bicts?\b|institui[cç][oõ]es cient[ií]ficas|pesquisadores|universidade|incubadoras|nits|apoiadas|grupos de pesquisa|spin-?off", req):
        perfis.append("ict_pesquisa")
    if re.search(r"mestr[ea]s?|doutor(?:es|as)?|p[oó]s-?gradua|stricto sensu|pesquisador(?:es)?|pipe|cientista|bolsa", texto):
        perfis.append("mestre_doutor")
    if re.search(r"estudantes|gradua[cç][aã]o|universit[aá]ri|rec[eé]m-?formad", req):
        perfis.append("estudantes")
    if re.search(r"dedica[cç][aã]o|dedicados|equipe com pelo menos|duas pessoas|2 pessoas|s[oó]cios", req):
        perfis.append("equipe_dedicada")
    if re.search(r"contrapartida|cofinanciamento|aporte pr[oó]prio", req):
        perfis.append("exige_contrapartida")
    if re.search(r"patente|propriedade intelectual|software registrado|inpi|tr[l]\s*[3-9]", texto):
        perfis.append("pi_patente")

    return {
        "ufs": ufs,
        "exige_cnpj": exige_cnpj,
        "aceita_pf": aceita_pf or not exige_cnpj,
        "setores": setores,
        "perfis": perfis,
    }


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
    validade_padrao_iso = (hoje + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%S.000Z')

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
            validade_item_iso = prazo_iso
            sem_data_final = False
            revisar = 0
            dias = (datetime.strptime(prazo, "%Y-%m-%d").date() - hoje.date()).days
        elif continuo:
            prazo_iso = None
            validade_item_iso = validade_padrao_iso
            sem_data_final = True
            revisar = 0
            dias = None
        else:
            # Sem prazo identificado e não é fluxo contínuo comprovado
            ignorados_sem_prazo += 1
            continue

        meta = extrair_metadados_match(e)
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
            "ufs": meta["ufs"],
            "exige_cnpj": meta["exige_cnpj"],
            "aceita_pf": meta["aceita_pf"],
            "setores": meta["setores"],
            "perfis": meta["perfis"],
            "validado_automaticamente": True,
            "validado_manualmente": False,
            "sem_data_final": sem_data_final,
            "prazo_iso": prazo_iso,
            "verificacao_valida_ate": validade_item_iso
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
