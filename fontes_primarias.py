"""Localiza links primários explícitos em notícias, sem usar notícias como prova de vigência."""
import re
import unicodedata
import json
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

class Ancoras(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.atual=None; self.rotulo=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.atual=dict(attrs).get('href'); self.rotulo=[]
    def handle_data(self, data):
        if self.atual: self.rotulo.append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self.atual:
            self.links.append((self.atual,' '.join(self.rotulo)))
            self.atual=None; self.rotulo=[]

def palavras(texto):
    texto=''.join(c for c in unicodedata.normalize('NFKD',texto.lower()) if not unicodedata.combining(c))
    genericas={'programa','startups','startup','inscricoes','abertas','edital','chamada','selecao',
               'brasil','primeira','segunda','turma','aceleracao','inovacao','para','empresas',
               'investimento','abre','novo','nova','publica','projetos','negocios'}
    return {p for p in re.findall(r'[a-z]{4,}',texto) if p not in genericas}

def selecionar_links(html, origem, titulo, oficial):
    parser=Ancoras();parser.feed(html)
    identidade=palavras(titulo)
    resultados=[]
    for href,rotulo in parser.links:
        alvo=urljoin(origem,href)
        p=urlsplit(alvo)
        if p.scheme not in ('http','https') or p.username or p.password or not oficial(alvo):
            continue
        if alvo.split('#')[0].rstrip('/') == origem.split('#')[0].rstrip('/'):
            continue
        if re.search(r'newsletter|privacidade|politica|login|signin|contato|subscribe', p.path, re.I):
            continue
        # A referência deve identificar o programa e apontar para sua participação/regras.
        termos=palavras(rotulo+' '+p.hostname+' '+p.path)
        comuns=identidade & termos
        comuns |= {pista for pista in identidade if pista in p.path.lower()}
        finalidade=re.search(r'edital|regulamento|inscri|inscre|candidat|apply|program|chamada|acelera|incuba|desafio',rotulo+' '+p.path,re.I)
        pdf_generico = (re.search(r'\.pdf(?:$|\?)', alvo, re.I) and
                        re.search(r'edital|regulamento|cronograma|aqui|download', rotulo, re.I))
        if (comuns and finalidade) or pdf_generico:
            resultados.append((len(comuns),alvo.split('#')[0]))
    unicos=[]
    for _,url in sorted(resultados,key=lambda x:-x[0]):
        if url not in unicos:unicos.append(url)
    return unicos[:3]

def fontes_do_indice(registro, oficial, caminho='data/triagem-descobertas.json'):
    titulo=registro.get('dados',{}).get('titulo') or registro.get('titulo','')
    termos=palavras(titulo)
    anos=set(re.findall(r'\b20\d{2}\b',titulo))
    if len(termos)<2:return []
    try:itens=json.loads(Path(caminho).read_text()).get('itens',[])
    except (OSError,ValueError):return []
    candidatos=[]
    for item in itens:
        url=item.get('url','')
        if url==registro['url'] or not oficial(url):continue
        nome=item.get('titulo','')
        edicao=set(re.findall(r'\b20\d{2}\b',nome))
        if anos and edicao and not anos & edicao:continue
        comuns=termos & palavras(nome)
        if len(comuns)>=2 and len(comuns)/len(termos)>=0.5:
            candidatos.append((len(comuns),url))
    return list(dict.fromkeys(url for _,url in sorted(candidatos,key=lambda x:-x[0])))[:3]

def localizar(registro, oficial):
    import radar
    try:
        ctype, bruto=radar.baixar(registro['url'])
        if bruto is None or 'html' not in ctype:return fontes_do_indice(registro,oficial)
        titulo=registro.get('dados',{}).get('titulo') or registro.get('titulo','')
        links=selecionar_links(bruto.decode('utf-8',errors='replace'),registro['url'],titulo,oficial)
        return links or fontes_do_indice(registro,oficial)
    except Exception:
        return fontes_do_indice(registro,oficial)


def carregar_fontes(caminho='data/fontes-primarias-descobertas.json'):
    """Registro de URLs, nunca decisões de vigência ou datas preenchidas."""
    try:
        dados=json.loads(Path(caminho).read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict):return {}
    from urllib.parse import urlsplit
    return {origem: alvo for origem, alvo in dados.items()
            if isinstance(origem, str) and isinstance(alvo, str)
            and urlsplit(origem).scheme in ('https', 'http')
            and urlsplit(alvo).scheme in ('https', 'http')
            and not urlsplit(alvo).username and not urlsplit(alvo).password}
