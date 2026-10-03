"""Datas e cronogramas em português/inglês, com vínculo à oportunidade."""
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from fontes_primarias import palavras

FUSO=ZoneInfo('America/Sao_Paulo')
MESES={'janeiro':1,'fevereiro':2,'marco':3,'abril':4,'maio':5,'junho':6,'julho':7,
       'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12,
       'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,'july':7,
       'august':8,'september':9,'october':10,'november':11,'december':12,
       'jan':1,'feb':2,'mar':3,'apr':4,'jun':6,'jul':7,'aug':8,'sep':9,'sept':9,'oct':10,'nov':11,'dec':12}

def limpo(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))

def datas(texto, ano=None):
    s=limpo(texto); achados=[]
    meses='|'.join(sorted(MESES,key=len,reverse=True))
    def incluir(m,dia,mes,year):
        if year is None:return
        try:achados.append((m.start(),datetime(int(year),int(mes),int(dia),23,59,59,tzinfo=FUSO)))
        except ValueError:pass
    for m in re.finditer(r'\b(20\d{2})-(\d{2})-(\d{2})\b',s):incluir(m,m[3],m[2],m[1])
    for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b',s):incluir(m,m[1],m[2],m[3])
    for m in re.finditer(r'\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:de\s+)?('+meses+r')\.?[,]?\s*(?:(?:de\s+)?(20\d{2}))?\b',s):
        incluir(m,m[1],MESES[m[2]],m[3] or ano)
    for m in re.finditer(r'\b('+meses+r')\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d{2}))?\b',s):
        incluir(m,m[2],MESES[m[1]],m[3] or ano)
    return [d for _,d in sorted(achados,key=lambda x:x[0])]


def ler_texto(ctype, bruto):
    import radar
    if 'pdf' in ctype:
        import io
        from pypdf import PdfReader
        return '\n'.join(p.extract_text(extraction_mode='layout') or '' for p in PdfReader(io.BytesIO(bruto)).pages)
    if b'<' not in bruto:return radar.para_texto(ctype,bruto)
    from bs4 import BeautifulSoup
    sopa=BeautifulSoup(bruto,'html.parser')
    # Um article que contém o título é a notícia; cartões não substituem o main.
    titulo=sopa.find('h1')
    artigo=titulo.find_parent('article') if titulo else None
    if artigo and len(artigo.get_text(' ',strip=True))<400:artigo=None
    corpos=sopa.select('[itemprop="articleBody"], .entry-content, .elementor-widget-theme-post-content')
    corpo=max(corpos,key=lambda t:len(t.get_text()),default=None)
    raiz=corpo or artigo or sopa.find('main') or max(sopa.find_all('article'), key=lambda t:len(t.get_text()), default=sopa)
    cabecalho=[]
    if titulo and titulo not in raiz.descendants:
        cabecalho.append(titulo.get_text(' ',strip=True))
    for meta in sopa.find_all('meta'):
        nome=meta.get('property') or meta.get('name') or ''
        if nome.lower() in ('article:published_time','datepublished','date','dc.date.issued'):
            valor=meta.get('content','')
            if valor:cabecalho.append('Data de publicação da página: '+valor)
    for tag in sopa.find_all('time'):
        if tag.get('datetime'):cabecalho.append('Data informada pela página: '+tag['datetime'])
    for tag in raiz(['script','style','nav','footer']):tag.decompose()
    # Mantém etapa e data da mesma linha de tabela juntas.
    for tr in raiz.find_all('tr'):
        texto=' | '.join(td.get_text(' ',strip=True) for td in tr.find_all(['th','td'],recursive=False))
        if texto:tr.replace_with('\n'+texto+'\n')
    # Um parágrafo não deve virar várias linhas por causa de links ou spans.
    for p in raiz.find_all('p'):p.replace_with('\n'+p.get_text(' ',strip=True)+'\n')
    return re.sub(r'\n{3,}','\n\n','\n'.join(cabecalho+[raiz.get_text('\n',strip=True)]))


def identidade(texto,titulo):
    termos=palavras(titulo)-{'edition','edicao','challenge','desafio','selecao','deep','techs','deeptechs','regiao','nordeste','processo'}
    comuns=termos & palavras(texto[:6000])
    return bool(termos) and len(comuns)>=min(2,len(termos))


def ano_edicao_documentada(texto,titulo):
    """Aceita ano explícito na identificação da edição, nunca em metadado de publicação."""
    for linha in [x.strip() for x in texto.splitlines()[:40] if x.strip()]:
        s=limpo(linha)
        if re.search(r'data de publicacao|data informada pela pagina|resultado|homolog',s):
            continue
        anos=re.findall(r'\b20\d{2}\b',s)
        if not anos:
            continue
        termos=palavras(titulo) & palavras(linha)
        identifica=identidade(linha,titulo) or (re.search(r'edital|chamada|programa|ciclo|turma',s) and termos)
        if identifica:
            return int(anos[0])
    return None


def prazo_documentado(texto,titulo):
    if not identidade(texto,titulo):return None
    linhas=[x.strip() for x in re.split(r'\n+|(?<=[.!?])\s+',texto) if x.strip()]
    fim=[]; inicio=[]
    for i,linha in enumerate(linhas):
        s=limpo(linha)
        if not re.search(r'inscri|inscrev|submiss|candidat|applications?|apply',s):continue
        if re.search(r'homolog|resultado|divulgacao|analise|finalistas|selected|results|winners',s):continue
        trecho=linha
        data_antes=False
        if i and len(linhas[i-1])<60 and datas(linhas[i-1]) and not re.search(r'[a-z]',re.sub(r'\b(?:'+ '|'.join(MESES) +r'|de|st|nd|rd|th)\b','',limpo(linhas[i-1]))):
            trecho=linhas[i-1]+'\n'+linha
            data_antes=True
        # Conecta apenas datas imediatamente abaixo de um rótulo, não a etapa seguinte.
        for proxima in ([] if data_antes else linhas[i+1:i+2]):
            if len(trecho)>900:break
            edicao_titulo=re.search(r'\b20\d{2}\b',titulo)
            if datas(proxima,int(edicao_titulo[0]) if edicao_titulo else None) and re.match(r'^[|:\s]*(?:\d{1,2}[/-]|20\d{2}-|\d{1,2}(?:st|nd|rd|th)?\s+(?:de\s+)?(?:'+ '|'.join(MESES) +r')\b|(?:'+ '|'.join(MESES) +r')\s+\d)',limpo(proxima)):
                trecho+='\n'+proxima
            else:break
        s=limpo(trecho)
        rotulo=bool(re.match(r'^(?:data (?:final|inicio) de submissao|inscricoes\b|periodo (?:de |das )?inscricoes|encerramento (?:de |das )?inscricoes|prazo (?:para |de )?submissao|applications? (?:close|deadline|open)|application deadline|submission deadline)',limpo(linha)))
        if datas(linha) and re.match(r'^(?:\d|'+ '|'.join(MESES) +r')\b',limpo(linha)) and re.search(r'applications? (?:close|open)|application deadline',limpo(linha)):
            rotulo=True
        if not identidade(trecho,titulo) and not rotulo:continue
        ds=datas(trecho)
        if ds:ds=datas(trecho,max(ds).year)
        # O ano pode estar no título da edição, nunca é presumido pelo dia atual.
        if not ds:
            edicao=re.search(r'\b20\d{2}\b',titulo)
            ano=int(edicao[0]) if edicao else ano_edicao_documentada(texto,titulo)
            if ano:ds=datas(trecho,ano)
        if not ds:continue
        abertura=bool(re.search(r'(?:applications?\s+(?:are\s+)?open|abert[ao]s?\s+a\s+partir|inicio\s+(?:das?\s+)?inscri|abertura\s+(?:das?\s+)?inscri)',s))
        fechamento=bool(re.search(r'data final de submissao|ate\b|prazo|encerr|termin|close|closing|deadline|until|through|ends?',s))
        periodo=len(ds)>=2 and bool(re.search(r'\s(?:a|ao|to|through)\s|\s[-–]\s',s))
        if fechamento or periodo:
            fim.append((max(ds),trecho))
            if periodo:inicio.append(min(ds))
        elif abertura:inicio.append(min(ds))
    if not fim:return None
    data,ev=max(fim,key=lambda x:x[0])
    return {'fim':data,'inicio':min(inicio).replace(hour=0,minute=0,second=0) if inicio else None,'evidencia':ev}
