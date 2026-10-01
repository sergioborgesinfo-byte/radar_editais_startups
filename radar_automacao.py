"""Verificação automática antes da publicação; não contém credenciais."""
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

VERSAO = "startup-automatico-v6"
FUSO = ZoneInfo("America/Sao_Paulo")
DOMINIOS = (
    "sebrae.com.br", "sebraestartups.com.br", "hubgoias.org",
    "acelera-hubgoias.innovc.com.br", "fapesc.sc.gov.br",
    "venturehub.se", "tecnosinos.com.br", "startup.google.com", "startup.google.com.br",
    "wow.ac", "darwinstartups.com", "aceventures.com.br", "fi.co",
    "usp.br", "unicamp.br", "ufpe.br", "ufmg.br", "pucminas.br", "unesp.br",
)
FONTES = (
    ("Finep Tecnologias Digitais — fonte oficial", "https://www.finep.gov.br/e/chamada-publica/222684/755485"),
    ("Formação GovTech — executor", "https://www.acelera-hubgoias.innovc.com.br/"),
    ("IT Potengi — edital oficial", "https://portal.ifrn.edu.br/documents/27992/EDITAL_332026compressed.pdf"),
    ("Canastra HUB — IFMG", "https://www.ifmg.edu.br/portal/noticias/canastra-hub-abre-inscricoes-para-pre-incubacao-e-incubacao-de-projetos-inovadores"),
)
INSTRUCOES = """
Além dos campos já solicitados, responda:
"fonte_responsavel": boolean,
"trecho_responsavel": citação literal da identificação do responsável,
"prazo_e_inscricao": boolean,
"prazo_hora": "HH:MM" ou null,
"identificador_edital": número/ano literal da chamada ou null,
"inscricoes_abertas": boolean,
"trecho_abertura": citação literal de inscrição atualmente aberta,
"sem_data_final": boolean.
Aceite programas de aceleração, incubação, desafios e seleção de investimento
para startups, mesmo sem a palavra edital. e_edital significa oportunidade concreta.
sem_data_final=true somente para inscrições abertas sem data final definida.
Não confunda newsletter, banco genérico de contatos ou "em breve" com seleção aberta.
Não use sem_data_final para ignorar uma data vencida. Em notícias antigas sem
situação atual verificável, inscricoes_abertas=false.
fonte_responsavel também pode ser notícia do próprio responsável sobre sua chamada.
fonte_responsavel=true somente para página/documento do responsável pela
chamada, executor ou plataforma oficial de inscrição. Notícias de terceiros,
apresentações gerais, agregadores e cópias de documentos não são fonte oficial.
Observe o domínio da URL e a identidade da instituição. Um PDF em site público
de outra instituição não é automaticamente a fonte responsável pela chamada.
trecho_responsavel deve existir literalmente no texto.
prazo_e_inscricao=true somente quando a data encerra a submissão de propostas
ou inscrições, não resultado, evento, vigência geral ou início da formação.
Se houver retificação, use o prazo final mais recente que estiver comprovado.
Em fluxo contínuo aceite uma data final apenas se o período de inscrição
estiver explicitamente delimitado no edital. Não transforme vigência em prazo.
prazo_hora deve estar no trecho_prazo; não presuma horário ausente.
identificador_edital deve ser literal; preserve edição e ano na identificação.
"""
SCHEMA = """
CREATE TABLE IF NOT EXISTS verificacoes_automaticas (
 edital_id TEXT PRIMARY KEY, url TEXT NOT NULL, versao TEXT NOT NULL,
 conferido_em TEXT NOT NULL, trecho_publico TEXT NOT NULL,
 trecho_prazo TEXT, trecho_responsavel TEXT NOT NULL,
 limite_iso TEXT, chave_edicao TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pendencias_automaticas (
 url TEXT PRIMARY KEY, titulo TEXT, orgao TEXT, motivo TEXT NOT NULL,
 tentado_em TEXT NOT NULL
);
"""
_visitadas = set()
_resolucoes = 0
_dominios = set(DOMINIOS)


def agora():
    return datetime.now(FUSO)


def normalizar(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def host(url):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or p.username or p.password:
        return ""
    return (p.hostname or "").lower().removeprefix("www.")


def institucional(url):
    h = host(url)
    return bool(h) and (
        h.endswith((".gov.br", ".edu.br"))
        or any(h == d or h.endswith("." + d) for d in _dominios)
    )


def preparar(con, cfg):
    global _resolucoes, _dominios
    con.executescript(SCHEMA)
    colunas = {x[1] for x in con.execute("PRAGMA table_info(verificacoes_automaticas)")}
    for nome, tipo in (("sem_data_final", "INTEGER DEFAULT 0"), ("trecho_abertura", "TEXT")):
        if nome not in colunas:
            con.execute(f"ALTER TABLE verificacoes_automaticas ADD COLUMN {nome} {tipo}")
    _visitadas.clear()
    _resolucoes = 0
    _dominios = set(DOMINIOS)
    # Domínios oficiais declarados nos programas pelo mantenedor do projeto.
    for p in cfg.get("programas", []):
        if p.get("ativo", True):
            for d in p.get("dominios", []):
                h = host("https://" + d)
                if h:
                    _dominios.add(h)
    fontes = cfg.setdefault("fontes", [])
    existentes = {f.get("url") for f in fontes}
    for nome, url in FONTES:
        if url not in existentes:
            fontes.insert(0, {"nome": nome, "url": url, "tipo": "pagina"})
    return cfg


def _pendente(con, url, motivo, d=None):
    d = d or {}
    con.execute(
        "INSERT OR REPLACE INTO pendencias_automaticas VALUES(?,?,?,?,?)",
        (url, d.get("titulo"), d.get("orgao"), motivo, agora().isoformat()),
    )
    con.execute("UPDATE editais SET revisar=1 WHERE url=?", (url,))
    con.commit()


def _literal(r, trecho, texto):
    return isinstance(trecho, str) and bool(trecho.strip()) and r.norm(trecho) in r.norm(texto)


def _responsavel(r, url, d, texto):
    if d.get("fonte_responsavel") is not True:
        return False
    if not institucional(url):
        h = host(url)
        genericos = {"instituto", "fundacao", "programa", "startup", "startups", "aceleradora", "incubadora", "brasil", "universidade", "inovacao", "tecnologia", "grupo", "centro"}
        marcas = [x for x in normalizar(d.get("orgao")).split() if len(x)>=6 and x not in genericos]
        # Novas instituições podem entrar sem cadastro prévio quando a marca
        # consta do domínio próprio e a extração comprova a fonte responsável.
        dominio = h.split(".")[0]
        if not h or not any(m in dominio for m in marcas):
            return False
    if not _literal(r, d.get("trecho_responsavel"), texto):
        return False
    orgao, h = normalizar(d.get("orgao")), host(url)
    # Não aceitar apresentações de terceiros como documentos dessas instituições.
    for nome, dominio in (("finep", "finep.gov.br"), ("ifrn", "ifrn.edu.br"), ("ifmg", "ifmg.edu.br")):
        if nome in orgao.split() and not (h == dominio or h.endswith("." + dominio)):
            return False
    return True


def _resolver(r, con, url, d, total):
    global _resolucoes
    chave = r.os.getenv("TAVILY_API_KEY")
    if not chave or _resolucoes >= 12:
        return False
    _resolucoes += 1
    consulta = f'{d.get("titulo", "")[:220]} {d.get("orgao", "")[:120]} edital inscrições site oficial'
    for candidato in r.buscar_aberta(consulta, 5, chave):
        if host(candidato) and candidato not in _visitadas:
            if processar(r, con, "Fonte oficial descoberta", candidato, total, resolver=False):
                return True
    return False


def abertura_explicita(trecho):
    s = normalizar(trecho)
    return bool(re.search(
        r"(?:pre )?inscric(?:oes|ao) (?:estao |esta )?abert|candidaturas (?:estao )?abertas|"
        r"recebendo (?:novas )?(?:propostas|inscricoes|candidaturas)|applications (?:are )?open|apply now", s
    )) and not re.search(r"encerrad|em breve|newsletter", s)


def processar(r, con, nome, url, total, resolver=True):
    if url in _visitadas:
        return False
    _visitadas.add(url)
    con.executescript(SCHEMA)
    try:
        ctype, conteudo = r.baixar(url)
        if conteudo is None:
            return False
        texto = r.para_texto(ctype, conteudo)
        h = hashlib.sha256((VERSAO + texto).encode()).hexdigest()
        visto = con.execute("SELECT hash FROM paginas WHERE url=?", (url,)).fetchone()
        conferido = con.execute(
            "SELECT conferido_em, sem_data_final FROM verificacoes_automaticas WHERE url=? AND versao=? ORDER BY conferido_em DESC LIMIT 1",
            (url, VERSAO),
        ).fetchone()
        if visto and visto["hash"] == h and conferido:
            if not conferido[1] and agora() - datetime.fromisoformat(conferido[0]) < timedelta(hours=22):
                total["ignorado"] += 1
                return True
        d = r.conferir_resposta(r.extrair(texto, url))
        publico = d.get("publico_startup") is True and _literal(r, d.get("trecho_publico"), texto)
        if d.get("e_edital") is not True or not publico:
            _pendente(con, url, "Público startup não comprovado", d)
            total["descartado"] = total.get("descartado", 0) + 1
            return False
        if not _responsavel(r, url, d, texto):
            _pendente(con, url, "Aguardando fonte responsável", d)
            if resolver:
                return _resolver(r, con, url, d, total)
            return False
        prazo_original = d.get("prazo_inscricao")
        d, revisar = r.validar(d, texto)
        if d.get("prazo_e_inscricao") is not True:
            d["prazo_inscricao"], revisar = None, True
        sem_data = (
            d.get("sem_data_final") is True and d.get("inscricoes_abertas") is True
            and not prazo_original
            and _literal(r, d.get("trecho_abertura"), texto)
            and abertura_explicita(d.get("trecho_abertura"))
        )
        if sem_data:
            revisar = False
        limite = None
        hora = d.get("prazo_hora")
        if hora is not None:
            if (not isinstance(hora, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", hora)
                    or hora not in (d.get("trecho_prazo") or "")):
                d["prazo_inscricao"], revisar = None, True
            elif d.get("prazo_inscricao"):
                limite = datetime.fromisoformat(d["prazo_inscricao"] + "T" + hora).replace(tzinfo=FUSO).isoformat()
        res = r.gravar(con, nome, url, d, revisar)
        eid = r.chave(d.get("orgao"), d.get("titulo"))
        codigo = d.get("identificador_edital")
        if not _literal(r, codigo, texto):
            codigo = None
        edicao = normalizar(d.get("orgao")) + "|" + normalizar(codigo or d.get("titulo"))
        con.execute(
            "INSERT OR REPLACE INTO verificacoes_automaticas(edital_id,url,versao,conferido_em,trecho_publico,trecho_prazo,trecho_responsavel,limite_iso,chave_edicao,sem_data_final,trecho_abertura) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (eid, url, VERSAO, agora().isoformat(), d["trecho_publico"],
             d.get("trecho_prazo"), d["trecho_responsavel"], limite, edicao, int(sem_data), d.get("trecho_abertura")),
        )
        con.execute("INSERT OR REPLACE INTO paginas VALUES(?,?,?)", (url, h, r._agora().isoformat()))
        if revisar:
            _pendente(con, url, "Prazo de inscrição não comprovado", d)
        else:
            con.execute("DELETE FROM pendencias_automaticas WHERE url=?", (url,))
            con.commit()
        total[res] += 1
        print(f'  {res}: {d.get("titulo")}' + (" [PENDENTE: não será publicado]" if revisar else " [fonte e prazo conferidos]"))
        return not revisar
    except Exception as e:
        con.rollback()
        total["erro"] += 1
        print(f"  erro em {url}: {e}")
        return False


def reconferir(r, con, total):
    con.executescript(SCHEMA)
    hoje = agora().date().isoformat()
    urls = [x[0] for x in con.execute(
        "SELECT DISTINCT e.url FROM editais e LEFT JOIN verificacoes_automaticas v ON v.edital_id=e.id WHERE e.revisar=0 AND (e.prazo>=? OR v.sem_data_final=1)", (hoje,)
    )]
    pendentes = [x[0] for x in con.execute(
        "SELECT url FROM pendencias_automaticas WHERE motivo!='Público startup não comprovado' ORDER BY tentado_em LIMIT 12"
    )]
    for url in dict.fromkeys(urls + pendentes):
        processar(r, con, "Reconferência automática", url, total)


def _duplicado(a, b):
    if a["url"] == b["url"] or a["chave_edicao"] == b["chave_edicao"]:
        return True
    if normalizar(a["orgao"]) != normalizar(b["orgao"]):
        return False
    ta, tb = normalizar(a["titulo"]), normalizar(b["titulo"])
    if re.findall(r"\d+", ta) != re.findall(r"\d+", tb):
        return False
    return SequenceMatcher(None, ta, tb).ratio() >= 0.92


def selecionados(con, versao=VERSAO):
    con.executescript(SCHEMA)
    limite = (agora() - timedelta(hours=48)).isoformat()
    linhas = con.execute(
        "SELECT e.*, v.limite_iso, v.chave_edicao, v.conferido_em, v.sem_data_final, v.trecho_abertura FROM editais e "
        "JOIN verificacoes_automaticas v ON v.edital_id=e.id AND v.url=e.url "
        "WHERE e.revisar=0 AND (e.prazo>=? OR (e.prazo IS NULL AND v.sem_data_final=1)) AND v.versao=? AND v.conferido_em>=? "
        "ORDER BY v.conferido_em DESC, e.atualizado_em DESC",
        (agora().date().isoformat(), versao, limite),
    ).fetchall()
    saida = []
    for e in linhas:
        if e["sem_data_final"] and not abertura_explicita(e["trecho_abertura"]):
            continue
        if e["sem_data_final"] and datetime.fromisoformat(e["conferido_em"]) < agora() - timedelta(hours=24):
            continue
        if e["limite_iso"] and datetime.fromisoformat(e["limite_iso"]) <= agora():
            continue
        if not any(_duplicado(e, outro) for outro in saida):
            saida.append(e)
    return saida
