#!/usr/bin/env python3
"""Radar de editais para startups.

Fluxo: coleta páginas das fontes -> detecta mudança por hash -> extrai campos
com IA (Claude) -> valida -> grava no SQLite -> exporta JSON para o front-end.

Uso:
  python radar.py run        # coleta as fontes e os programas e atualiza o banco
  python radar.py descobrir  # (re)busca na web as páginas oficiais dos programas
  python radar.py descobertas# mostra as páginas que a busca encontrou
  python radar.py export     # gera editais.json (formato do protótipo)
  python radar.py revisar    # lista editais que precisam de conferência humana
"""
import argparse
import hashlib
import io
import json
import os
import re
import socket
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup


def _carregar_env():
    """Lê o arquivo .env (CHAVE=valor) que fica ao lado do radar.py."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    try:
        with open(caminho, encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if linha and not linha.startswith("#") and "=" in linha:
                    k, v = linha.split("=", 1)
                    v = v.strip().strip('"').strip("'")
                    if v:
                        os.environ.setdefault(k.strip(), v)
    except FileNotFoundError:
        pass


_carregar_env()

DB = os.getenv("RADAR_DB", "radar.db")
MODEL = os.getenv("RADAR_MODEL", "claude-haiku-4-5-20251001")
UA = f"RadarEditaisBot/0.1 (+contato: {os.getenv('RADAR_EMAIL') or 'troque-por-seu-email@exemplo.com'})"
DESCOBRIR_DIAS = 7  # refaz a busca de cada programa a cada 7 dias
socket.setdefaulttimeout(30)  # nenhuma conexão (nem o robots.txt) trava por mais de 30 s
PAUSA = 2.0  # segundos entre requisições, para não sobrecarregar os sites
MAX_CHARS = 30000


def _agora():
    return datetime.now(timezone.utc).replace(tzinfo=None)

CHAVES = re.compile(
    r"edital|chamada|sele[cç][aã]o|inscri[cç][oõ]es|fomento|subven[cç][aã]o|incuba|acelera",
    re.I,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS paginas(url TEXT PRIMARY KEY, hash TEXT, visto_em TEXT);
CREATE TABLE IF NOT EXISTS editais(
  id TEXT PRIMARY KEY, url TEXT, fonte TEXT, titulo TEXT, orgao TEXT, tipo TEXT,
  estagio TEXT, descricao TEXT, valor REAL, prazo TEXT, requisitos TEXT,
  trecho_prazo TEXT, revisar INTEGER, criado_em TEXT, atualizado_em TEXT);
CREATE TABLE IF NOT EXISTS descobertas(
  programa TEXT, url TEXT, motivo TEXT, achado_em TEXT, PRIMARY KEY(programa, url));
CREATE TABLE IF NOT EXISTS buscas(programa TEXT PRIMARY KEY, feita_em TEXT);
CREATE TABLE IF NOT EXISTS consultas_feitas(consulta TEXT PRIMARY KEY, feita_em TEXT);
CREATE TABLE IF NOT EXISTS mudancas(
  id INTEGER PRIMARY KEY AUTOINCREMENT, edital_id TEXT, campo TEXT,
  antigo TEXT, novo TEXT, em TEXT);
"""

PROMPT = """Você extrai dados estruturados de editais e chamadas públicas para startups no Brasil.
Responda APENAS com um objeto JSON, sem texto extra e sem markdown, com estes campos:
{
 "e_edital": true|false,            // false se for notícia, página institucional ou resultado
 "titulo": string,
 "orgao": string,                   // quem publica o edital
 "tipo": "Subvenção"|"Crédito"|"Incubação"|"Aceleração"|"Bolsa"|"Prêmio"|"Inovação aberta"|"Outro",
 "estagio": "Ideação e MVP"|"Tração"|"Escala"|"Qualquer",
 "descricao": string,               // até 200 caracteres, em português simples
 "valor_maximo_reais": number|null,
 "prazo_inscricao": "AAAA-MM-DD"|null,
 "trecho_prazo": string|null,       // cópia LITERAL do trecho do texto que informa o prazo
 "requisitos": string|null          // até 300 caracteres
}
Regras: não invente nada. Se a informação não estiver no texto, use null.
Se houver várias datas, use o fim das inscrições. Hoje é {hoje}."""


# ---------- banco ----------
def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


# ---------- coleta ----------
_robots = {}


def permitido(url):
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            rp.read()
        except Exception:
            rp = None
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(UA, url)


def baixar(url):
    if not permitido(url):
        print(f"  bloqueado pelo robots.txt: {url}")
        return None, None
    time.sleep(PAUSA)
    r = requests.get(url, headers={"User-Agent": UA}, timeout=(10, 30))
    r.raise_for_status()
    return r.headers.get("content-type", ""), r.content


def para_texto(ctype, conteudo):
    if "pdf" in ctype.lower():
        from pypdf import PdfReader

        leitor = PdfReader(io.BytesIO(conteudo))
        return "\n".join((p.extract_text() or "") for p in leitor.pages)
    sopa = BeautifulSoup(conteudo, "html.parser")
    for tag in sopa(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return re.sub(r"\n{3,}", "\n\n", sopa.get_text("\n", strip=True))


def candidatos(fonte):
    """Devolve as URLs a processar para uma fonte."""
    if fonte.get("tipo") == "pagina":
        return [fonte["url"]]
    ctype, conteudo = baixar(fonte["url"])
    if conteudo is None:
        return []
    if "pdf" in ctype.lower():
        return [fonte["url"]]
    sopa = BeautifulSoup(conteudo, "html.parser")
    achados = [fonte["url"]]  # a própria página também pode ser um edital
    for a in sopa.find_all("a", href=True):
        href = urljoin(fonte["url"], a["href"]).split("#")[0]
        if not href.startswith("http"):
            continue
        mesmo_site = urlparse(href).netloc == urlparse(fonte["url"]).netloc
        if mesmo_site and (CHAVES.search(a.get_text(" ")) or CHAVES.search(href)):
            if href not in achados:
                achados.append(href)
    return achados[: fonte.get("max_links", 30) + 1]


# ---------- extração com IA ----------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
_ultima_chamada = [0.0]


def _limpar_json(bruto):
    bruto = re.sub(r"^\x60{3}(?:json)?|\x60{3}$", "", bruto.strip(), flags=re.M).strip()
    return json.loads(bruto)


def extrair_gemini(texto, url, chave):
    """Extração pelo Gemini (plano gratuito do Google AI Studio)."""
    corpo = {
        "systemInstruction": {"parts": [{"text": PROMPT.replace("{hoje}", date.today().isoformat())}]},
        "contents": [{"role": "user", "parts": [{"text": f"URL: {url}\n\nTEXTO:\n{texto[:MAX_CHARS]}"}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    for tentativa in range(4):
        espera = 7 - (time.time() - _ultima_chamada[0])  # respeita o limite por minuto
        if espera > 0:
            time.sleep(espera)
        _ultima_chamada[0] = time.time()
        r = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": chave, "Content-Type": "application/json"},
            json=corpo,
            timeout=90,
        )
        if r.status_code == 429:
            time.sleep(20 * (tentativa + 1))
            continue
        r.raise_for_status()
        partes = r.json()["candidates"][0]["content"]["parts"]
        return _limpar_json("".join(x.get("text", "") for x in partes))
    raise RuntimeError("limite gratuito do Gemini atingido; a página será tentada de novo na próxima execução")


def extrair(texto, url):
    chave = os.getenv("GEMINI_API_KEY")
    if chave:
        return extrair_gemini(texto, url, chave)
    return extrair_anthropic(texto, url)


def extrair_anthropic(texto, url):
    import anthropic

    cliente = anthropic.Anthropic()  # usa ANTHROPIC_API_KEY do ambiente
    resp = cliente.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=PROMPT.replace("{hoje}", date.today().isoformat()),
        messages=[{"role": "user", "content": f"URL: {url}\n\nTEXTO:\n{texto[:MAX_CHARS]}"}],
    )
    bruto = "".join(b.text for b in resp.content if b.type == "text")
    bruto = re.sub(r"^\x60{3}(?:json)?|\x60{3}$", "", bruto.strip(), flags=re.M).strip()
    return json.loads(bruto)


def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def validar(d, texto):
    """Devolve (dados limpos, precisa_revisar)."""
    revisar = False
    prazo = d.get("prazo_inscricao")
    try:
        datetime.strptime(prazo, "%Y-%m-%d")
    except (TypeError, ValueError):
        prazo, revisar = None, True
    trecho = d.get("trecho_prazo")
    # Guarda contra alucinação: o trecho citado precisa existir no texto original.
    if not trecho or norm(trecho) not in norm(texto):
        revisar = True
    d["prazo_inscricao"] = prazo
    return d, revisar


# ---------- gravação ----------
def chave(orgao, titulo):
    base = re.sub(r"[^a-z0-9]+", " ", norm(orgao) + "|" + norm(titulo))
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def gravar(con, fonte, url, d, revisar):
    agora = _agora().isoformat(timespec="seconds")
    eid = chave(d.get("orgao"), d.get("titulo"))
    novo = {
        "titulo": d.get("titulo"), "orgao": d.get("orgao"), "tipo": d.get("tipo"),
        "estagio": d.get("estagio"), "descricao": d.get("descricao"),
        "valor": d.get("valor_maximo_reais"), "prazo": d.get("prazo_inscricao"),
        "requisitos": d.get("requisitos"), "trecho_prazo": d.get("trecho_prazo"),
    }
    antigo = con.execute("SELECT * FROM editais WHERE id=?", (eid,)).fetchone()
    if antigo is None:
        con.execute(
            "INSERT INTO editais VALUES(:id,:url,:fonte,:titulo,:orgao,:tipo,:estagio,"
            ":descricao,:valor,:prazo,:requisitos,:trecho_prazo,:revisar,:agora,:agora)",
            {**novo, "id": eid, "url": url, "fonte": fonte, "revisar": int(revisar), "agora": agora},
        )
        return "novo"
    for campo in ("prazo", "valor"):
        if str(antigo[campo]) != str(novo[campo]) and novo[campo] is not None:
            con.execute(
                "INSERT INTO mudancas(edital_id,campo,antigo,novo,em) VALUES(?,?,?,?,?)",
                (eid, campo, antigo[campo], novo[campo], agora),
            )
    con.execute(
        "UPDATE editais SET url=?,titulo=?,tipo=?,estagio=?,descricao=?,valor=?,prazo=?,"
        "requisitos=?,trecho_prazo=?,revisar=?,atualizado_em=? WHERE id=?",
        (url, novo["titulo"], novo["tipo"], novo["estagio"], novo["descricao"], novo["valor"],
         novo["prazo"], novo["requisitos"], novo["trecho_prazo"], int(revisar), agora, eid),
    )
    return "atualizado"


# ---------- descoberta por nome de programa ----------
PROMPT_BUSCA = """Você localiza páginas OFICIAIS de editais e chamadas públicas para startups no Brasil.
Use a busca na web para encontrar a(s) página(s) oficial(is) das chamadas abertas, ou mais recentes, do programa indicado.
Prefira o site do próprio programa ou da instituição que o realiza (.gov.br, .org.br, universidades, empresas). Evite blogs e agregadores.
Responda APENAS com JSON: {"paginas":[{"url":string,"motivo":string}]} com no máximo 3 itens.
Use somente URLs que apareceram nos resultados da busca. Se não achar nada confiável, responda {"paginas":[]}. Hoje é {hoje}."""


SOCIAIS = ("facebook.com", "instagram.com", "linkedin.com", "youtube.com", "twitter.com", "x.com", "tiktok.com")


RUIDO = ("cbinsights.com", "crunchbase.com")


def _corpo_tavily(consulta, prog):
    corpo = {
        "query": consulta,
        "max_results": 6,
        "search_depth": "basic",
        "exclude_domains": list(SOCIAIS + RUIDO),
    }
    if prog.get("dominios"):  # só sites oficiais informados no sources.json
        corpo["include_domains"] = prog["dominios"]
    return corpo


def buscar_tavily(prog, chave):
    """Busca gratuita via Tavily (1.000 créditos/mês no plano free)."""
    consulta = f"{prog.get('busca', prog['nome'])} edital chamada inscrições {date.today().year}"
    r = requests.post(
        "https://api.tavily.com/search",
        headers={"Authorization": f"Bearer {chave}"},
        json=_corpo_tavily(consulta, prog),
        timeout=30,
    )
    r.raise_for_status()
    achados = []
    for item in r.json().get("results", []):
        host = urlparse(item["url"]).netloc.lower()
        if host.endswith(SOCIAIS + RUIDO):
            continue
        achados.append({"url": item["url"], "motivo": item.get("title", "")})
    return achados[:4]


def buscar_anthropic(prog):
    """Busca pela ferramenta de busca na web da API do Claude (cobrada por pesquisa)."""
    import anthropic

    cliente = anthropic.Anthropic()
    resp = cliente.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=PROMPT_BUSCA.replace("{hoje}", date.today().isoformat()),
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}],
        messages=[{"role": "user", "content": f"Programa: {prog.get('busca', prog['nome'])}"}],
    )
    # Só aceitamos URLs que realmente apareceram nos resultados da busca (evita link inventado).
    vistos = set()
    for b in resp.content:
        if b.type == "web_search_tool_result" and isinstance(b.content, list):
            vistos.update(r.url for r in b.content if getattr(r, "url", None))
    texto = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\}", texto, re.S)
    achados = json.loads(m.group(0)).get("paginas", []) if m else []
    return [a for a in achados if a.get("url") in vistos]


def descobrir(con, prog):
    """Acha as páginas oficiais de um programa e guarda no banco.
    Usa Tavily se TAVILY_API_KEY existir; senão, a busca do Claude."""
    nome = prog["nome"]
    chave = os.getenv("TAVILY_API_KEY")
    validos = buscar_tavily(prog, chave) if chave else buscar_anthropic(prog)
    agora = _agora().isoformat(timespec="seconds")
    if validos:
        con.execute("DELETE FROM descobertas WHERE programa=?", (nome,))
    for a in validos:
        con.execute(
            "INSERT OR REPLACE INTO descobertas VALUES(?,?,?,?)",
            (nome, a["url"], a.get("motivo", ""), agora),
        )
    con.execute("INSERT OR REPLACE INTO buscas VALUES(?,?)", (nome, agora))
    con.commit()
    return len(validos)


def urls_programa(con, prog):
    if prog.get("url"):  # URL fixa informada por você tem prioridade
        return [prog["url"]]
    ult = con.execute("SELECT feita_em FROM buscas WHERE programa=?", (prog["nome"],)).fetchone()
    velho = ult is None or datetime.fromisoformat(ult["feita_em"]) < _agora() - timedelta(days=DESCOBRIR_DIAS)
    if velho:
        try:
            n = descobrir(con, prog)
            print(f"  busca: {n} página(s) encontrada(s)")
        except Exception as e:
            print(f"  erro na busca: {e}")
    return [r["url"] for r in con.execute("SELECT url FROM descobertas WHERE programa=?", (prog["nome"],))]


# ---------- busca aberta (sem saber os sites de antemão) ----------
def buscar_aberta(consulta, n, chave):
    """Busca livre na web pela Tavily; devolve as URLs dos resultados."""
    corpo = {
        "query": consulta,
        "max_results": n,
        "search_depth": "basic",
        "time_range": "month",
        "exclude_domains": list(SOCIAIS + RUIDO),
    }

    def enviar(c):
        return requests.post(
            "https://api.tavily.com/search",
            headers={"Authorization": f"Bearer {chave}"},
            json=c,
            timeout=30,
        )

    r = enviar(corpo)
    if r.status_code in (400, 422):  # se o filtro de data não for aceito, tenta sem ele
        corpo.pop("time_range")
        r = enviar(corpo)
    r.raise_for_status()
    urls = []
    for item in r.json().get("results", []):
        host = urlparse(item["url"]).netloc.lower()
        if not host.endswith(SOCIAIS + RUIDO):
            urls.append(item["url"])
    return urls


def busca_aberta(con, cfg, total):
    ba = cfg.get("busca_aberta")
    chave = os.getenv("TAVILY_API_KEY")
    if not ba or not chave:
        return
    feitas = {r["consulta"]: r["feita_em"] for r in con.execute("SELECT consulta, feita_em FROM consultas_feitas")}
    # rodízio: primeiro as consultas nunca feitas, depois as mais antigas
    ordem = sorted(ba.get("consultas", []), key=lambda c: feitas.get(c, ""))
    for modelo in ordem[: ba.get("por_execucao", 6)]:
        consulta = modelo.replace("{ano}", str(date.today().year))
        print(f"Busca aberta: {consulta}")
        try:
            urls = buscar_aberta(consulta, ba.get("resultados", 5), chave)
        except Exception as e:
            print(f"  erro na busca: {e}")
            continue
        con.execute("INSERT OR REPLACE INTO consultas_feitas VALUES(?,?)", (modelo, _agora().isoformat(timespec="seconds")))
        con.commit()
        for url in urls:
            processar_url(con, "Busca aberta", url, total)


def _hosts_conhecidos(cfg):
    conhecidos = set()
    for f in cfg.get("fontes", []):
        conhecidos.add(urlparse(f["url"]).netloc.lower().removeprefix("www."))
    for pr in cfg.get("programas", []):
        if pr.get("url"):
            conhecidos.add(urlparse(pr["url"]).netloc.lower().removeprefix("www."))
        for d in pr.get("dominios", []):
            conhecidos.add(d.lower().removeprefix("www."))
    return conhecidos


def cmd_sugestoes(args):
    """Sites novos que a busca aberta encontrou publicando editais."""
    con = conectar()
    with open(args.fontes, encoding="utf-8") as f:
        cfg = json.load(f)
    conhecidos = _hosts_conhecidos(cfg)
    cont = {}
    for r in con.execute("SELECT url FROM editais WHERE fonte='Busca aberta'"):
        h = urlparse(r["url"]).netloc.lower().removeprefix("www.")
        if not any(h == c or h.endswith("." + c) for c in conhecidos):
            cont[h] = cont.get(h, 0) + 1
    if not cont:
        print("Nenhuma sugestão ainda.")
    for h, n in sorted(cont.items(), key=lambda x: -x[1]):
        print(f"{n} edital(is)  {h}")
    if cont:
        print("\nPara acompanhar um deles de forma fixa: python radar.py aprovar SITE")


def cmd_aprovar(args):
    con = conectar()
    with open(args.fontes, encoding="utf-8") as f:
        cfg = json.load(f)
    alvo = args.site.lower().removeprefix("www.")
    achado = None
    for r in con.execute("SELECT url FROM editais WHERE fonte='Busca aberta'"):
        if urlparse(r["url"]).netloc.lower().removeprefix("www.") == alvo:
            achado = r["url"]
            break
    if not achado:
        print("Site não encontrado entre as descobertas. Veja a lista com: python radar.py sugestoes")
        return
    cfg.setdefault("fontes", []).append({"nome": alvo, "url": achado, "tipo": "listagem", "max_links": 10})
    with open(args.fontes, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"Adicionado às fontes fixas: {alvo} ({achado})")


def cmd_buscar(args):
    con = conectar()
    with open(args.fontes, encoding="utf-8") as f:
        cfg = json.load(f)
    total = {"novo": 0, "atualizado": 0, "ignorado": 0, "erro": 0}
    busca_aberta(con, cfg, total)
    print("Resumo:", total)


# ---------- comandos ----------
def processar_url(con, nome, url, total):
    try:
        ctype, conteudo = baixar(url)
        if conteudo is None:
            return
        texto = para_texto(ctype, conteudo)
        h = hashlib.sha256(texto.encode()).hexdigest()
        visto = con.execute("SELECT hash FROM paginas WHERE url=?", (url,)).fetchone()
        if visto and visto["hash"] == h:
            total["ignorado"] += 1  # página não mudou: não gasta chamada de IA
            return
        dados = extrair(texto, url)
        con.execute(
            "INSERT OR REPLACE INTO paginas VALUES(?,?,?)",
            (url, h, _agora().isoformat(timespec="seconds")),
        )
        if dados.get("e_edital"):
            dados, revisar = validar(dados, texto)
            res = gravar(con, nome, url, dados, revisar)
            total[res] += 1
            print(f"  {res}: {dados.get('titulo')}" + ("  [REVISAR]" if revisar else ""))
        con.commit()
    except Exception as e:
        total["erro"] += 1
        print(f"  erro em {url}: {e}")


def cmd_run(args):
    con = conectar()
    with open(args.fontes, encoding="utf-8") as f:
        cfg = json.load(f)
    total = {"novo": 0, "atualizado": 0, "ignorado": 0, "erro": 0}
    for fonte in [x for x in cfg.get("fontes", []) if x.get("ativo", True)]:
        print(f"Fonte: {fonte['nome']}")
        try:
            urls = candidatos(fonte)
        except Exception as e:
            print(f"  erro ao listar: {e}")
            total["erro"] += 1
            continue
        for url in urls:
            processar_url(con, fonte["nome"], url, total)
    for prog in [x for x in cfg.get("programas", []) if x.get("ativo", True)]:
        print(f"Programa: {prog['nome']}")
        for base in urls_programa(con, prog):
            try:
                urls = candidatos({"url": base, "tipo": "listagem", "max_links": 3})
            except Exception as e:
                print(f"  erro ao abrir {base}: {e}")
                total["erro"] += 1
                continue
            for url in urls:
                processar_url(con, prog["nome"], url, total)
    busca_aberta(con, cfg, total)
    print("Resumo:", total)


def cmd_descobrir(args):
    con = conectar()
    with open(args.fontes, encoding="utf-8") as f:
        cfg = json.load(f)
    for prog in [x for x in cfg.get("programas", []) if x.get("ativo", True) and not x.get("url")]:
        print(f"Buscando: {prog['nome']}")
        try:
            print(f"  {descobrir(con, prog)} página(s) encontrada(s)")
        except Exception as e:
            print(f"  erro: {e}")


def cmd_descobertas(args):
    con = conectar()
    for r in con.execute("SELECT programa, url, motivo FROM descobertas ORDER BY programa"):
        print(f"- {r['programa']}\n  {r['url']}\n  {r['motivo']}")


def cmd_export(args):
    con = conectar()
    hoje = date.today()
    saida = []
    for e in con.execute("SELECT * FROM editais WHERE prazo IS NOT NULL"):
        dias = (datetime.strptime(e["prazo"], "%Y-%m-%d").date() - hoje).days
        if dias < -30:  # esconde editais encerrados há mais de 30 dias
            continue
        criado = datetime.fromisoformat(e["criado_em"]).date()
        prorrogado = con.execute(
            "SELECT 1 FROM mudancas WHERE edital_id=? AND campo='prazo' AND novo>antigo AND em>?",
            (e["id"], (hoje - timedelta(days=14)).isoformat()),
        ).fetchone()
        saida.append({
            "t": e["titulo"], "o": e["orgao"], "tipo": e["tipo"], "est": e["estagio"],
            "v": e["valor"] or 0, "prazo": e["prazo"], "d": dias, "desc": e["descricao"], "link": e["url"],
            "n": int((hoje - criado).days <= 7), "r": int(bool(prorrogado)),
            "revisar": e["revisar"],
        })
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)
    print(f"{len(saida)} editais exportados para {args.saida}")


def cmd_revisar(args):
    con = conectar()
    for e in con.execute("SELECT titulo, orgao, prazo, trecho_prazo, url FROM editais WHERE revisar=1"):
        print(f"- {e['titulo']} ({e['orgao']})\n  prazo: {e['prazo']}  trecho: {e['trecho_prazo']}\n  {e['url']}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--fontes", default="sources.json")
    r.set_defaults(fn=cmd_run)
    x = sub.add_parser("export")
    x.add_argument("--saida", default="editais.json")
    x.set_defaults(fn=cmd_export)
    v = sub.add_parser("revisar")
    v.set_defaults(fn=cmd_revisar)
    d = sub.add_parser("descobrir")
    d.add_argument("--fontes", default="sources.json")
    d.set_defaults(fn=cmd_descobrir)
    l = sub.add_parser("descobertas")
    l.set_defaults(fn=cmd_descobertas)
    bu = sub.add_parser("buscar")
    bu.add_argument("--fontes", default="sources.json")
    bu.set_defaults(fn=cmd_buscar)
    su = sub.add_parser("sugestoes")
    su.add_argument("--fontes", default="sources.json")
    su.set_defaults(fn=cmd_sugestoes)
    ap = sub.add_parser("aprovar")
    ap.add_argument("site")
    ap.add_argument("--fontes", default="sources.json")
    ap.set_defaults(fn=cmd_aprovar)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
