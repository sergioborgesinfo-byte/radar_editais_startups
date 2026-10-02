"""Localiza links primários explícitos em notícias, sem usar notícias como prova de vigência."""
import re
import unicodedata
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
        # A referência deve identificar o programa e apontar para sua participação/regras.
        termos=palavras(rotulo+' '+p.hostname+' '+p.path)
        comuns=identidade & termos
        comuns |= {pista for pista in identidade if pista in p.path.lower()}
        finalidade=re.search(r'edital|regulamento|inscri|inscre|candidat|apply|program|chamada|acelera|incuba|desafio',rotulo+' '+p.path,re.I)
        if comuns and finalidade:
            resultados.append((len(comuns),alvo.split('#')[0]))
    unicos=[]
    for _,url in sorted(resultados,key=lambda x:-x[0]):
        if url not in unicos:unicos.append(url)
    return unicos[:3]

def localizar(registro, oficial):
    import radar
    try:
        ctype, bruto=radar.baixar(registro['url'])
        if bruto is None or 'html' not in ctype:return []
        titulo=registro.get('dados',{}).get('titulo') or registro.get('titulo','')
        return selecionar_links(bruto.decode('utf-8',errors='replace'),registro['url'],titulo,oficial)
    except Exception:
        return []
