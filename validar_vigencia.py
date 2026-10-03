"""Valida edição, público e prazo; publica somente oportunidades abertas comprovadas."""
import json
import os
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from sebrae_programas import ler_programa, texto_programa

FUSO = ZoneInfo('America/Sao_Paulo')
MERCOPAR = 'https://programas.sebraestartups.com.br/in/1783963246760x826977266273542100'
FONTES_OFICIAIS = {
    'https://prefeitura.rio/cidade/invest-rio-e-maravalley-lancam-edital-para-selecionar-dez-startups-para-missao-web-summit-lisboa-2026':
        'https://www.maravalley.rio/programas/web-summit-lisboa-2026',
    'https://fapesc.sc.gov.br/edital-de-chamada-publica-fapesc-n-o-31-2026-programa-acelera-startup-sc-6a-edicao':
        'https://fapesc.sc.gov.br/edital-de-chamada-publica-fapesc-n-o-31-2026-programa-acelera-startup-sc-6a-edicao',
    'https://www.darwinstartups.com/icmlab':
        'https://www.darwinstartups.com/icmlab',
    'https://www.santacatarinaempauta.com.br/2026/05/05/programa-nascer-abre-inscricoes-para-transformar-ideias-em-startups':
        'https://fapesc.sc.gov.br/edital-de-chamada-publica-fapesc-n-o-24-2026-programa-nascer-de-pre-incubacao-de-ideias-inovadoras-para-o-ecossistema-catarinense-de-inovacao-vii-edicao/',
    'https://jornaldigital.recife.br/2026/02/19/sua-ideia-pode-ser-a-proxima-startup-gigante-inscricoes-abertas-para-pre-incubacao-do-porto-digital':
        'https://novosite.portodigital.org/noticia/inscricoes-prorrogadas-para-programas-early-stage/',
    'https://rtm.net.br/darwin-startups-abre-inscricoes-para-15a-turma-de-aceleracao':
        'https://www.darwinstartups.com/batch15',
    'https://convergenciadigital.com.br/mercado/programa-rio-ia-2026-vai-investir-r-640-mil-em-startups':
        'https://prosas.com.br/editais/16756-1o-edital-para-o-programa-de-inovacao-aberta-do-hub-rio-ia-2026?subdominio=prosas',
    'https://dana.com.br/canaldana/2024/07/25/randoncorp-abre-inscricoes-para-segunda-turma-do-programa-de-aceleracao-de-startups':
        'https://www.randoncorp.com/pt/blog/rv-abre-inscri%C3%A7%C3%B5es-para-a-nova-turma-de-acelera%C3%A7%C3%A3o-de-startups/',
    'https://www.startupsc.com.br/programa-de-capacitacao-startup-sc':
        'https://www.startupsc.com.br/inscreva-se/',
}
# Fontes alternativas identificadas; datas continuam sendo lidas e comprovadas.
try:
    from fontes_primarias import carregar_fontes
    FONTES_OFICIAIS.update(carregar_fontes())
except (OSError, ValueError):
    pass
MESES = {'janeiro':1,'fevereiro':2,'marco':3,'abril':4,'maio':5,'junho':6,
         'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}


def normalizar(s):
    s = ''.join(c for c in unicodedata.normalize('NFKD', str(s).lower())
                if not unicodedata.combining(c))
    return re.sub(r'\W+', ' ', s).strip()


@lru_cache(maxsize=1)
def dominios_configurados():
    try:
        configuracao = json.loads(Path('sources.json').read_text())
    except (OSError, ValueError):
        return set()
    dominios = set()
    for registro in configuracao.get('fontes', []) + configuracao.get('programas', []):
        dominios.update(d.lower().removeprefix('www.') for d in registro.get('dominios', []))
        host = urlsplit(registro.get('url', '')).hostname
        if host:
            dominios.add(host.lower().removeprefix('www.'))
    return dominios


def oficial(url):
    host = (urlsplit(url).hostname or '').lower()
    dominios = ('sebrae.com.br', 'agenciasebrae.com.br', 'sebraestartups.com.br',
                'fapemig.br', 'fapesc.sc.gov.br', 'finep.gov.br', 'google.com',
                'grupoboticario.com.br', 'natura.com.br', 'randoncorp.com',
                'startupbrasil.org.br', 'cbamazonia.org', 'darwinstartups.com',
                'suzano.com.br', 'tecnosinos.com.br', 'senai.br', 'ufla.br',
                'fapesp.br', 'feevale.br', 'prefeitura.rio', 'maravalley.rio', 'hello-tomorrow.org',
                'inatel.br', 'portodigital.org', 'startupsc.com.br')
    return (host.endswith(('.gov.br', '.gov.pt', '.edu.br', '.org.br')) or
            any(host == d or host.endswith('.' + d) for d in set(dominios) | dominios_configurados()))


def dados_sebrae(url, abrir=urlopen):
    return ler_programa(url, abrir)


def validar_sebrae(registro, agora, abrir=urlopen):
    url = registro['url']
    try:
        dados = dados_sebrae(url, abrir)
    except Exception:
        return {'url': url, 'status': 'pendente_acesso', 'motivo': 'fonte_oficial_indisponivel'}
    if not dados:
        return {'url': url, 'status': 'pendente_acesso', 'motivo': 'dados_dinamicos_ausentes'}
    titulo = dados.get('titulo_text') or registro.get('titulo', '')
    fim_ms = dados.get('data_final_date')
    inicio_ms = dados.get('data_inicio_date')
    ativo = dados.get('ativo_boolean') is True
    texto = texto_programa(dados)
    publico = bool(re.search(r'\bstartups?\b|\bdeep\s*techs?\b|empreendedores? inovadores?|neg[oó]cios inovadores?', texto, re.I))
    concreta = bool(re.search(r'programa|miss[aã]o|rodada|exposi[cç][aã]o|feira|evento|edital|pr[eê]mio|chamada|cadastro|incuba|acelera|jornada|capital empreendedor|manifesta[cç][aã]o de interesse', titulo + ' ' + dados.get('descricao_breve_text', ''), re.I))
    edicao = re.search(r'\b20\d{2}\b', titulo)
    if not (publico and concreta and isinstance(fim_ms, (int, float))):
        return {'url': url, 'status': 'pendente_evidencia',
                'motivo': 'edicao_publico_atividade_ou_prazo_nao_comprovado'}
    fim = datetime.fromtimestamp(fim_ms / 1000, FUSO)
    inicio = datetime.fromtimestamp(inicio_ms / 1000, FUSO) if isinstance(inicio_ms, (int, float)) else None
    if fim <= agora:
        return {'url': url, 'status': 'encerrada', 'prazo_iso': fim.isoformat(),
                'evidencia_prazo': f'data_final_date={int(fim_ms)}'}
    if not ativo:
        return {'url': url, 'titulo': titulo, 'status': 'pendente_evidencia',
                'motivo': 'inscricoes_nao_ativas_na_fonte'}
    if inicio and inicio > agora:
        return {'url': url, 'titulo': titulo, 'status': 'ainda_nao_aberta',
                'inicio_iso': inicio.isoformat(), 'prazo_iso': fim.isoformat()}
    modalidade = ('Cadastro de interesse' if re.search(r'cadastro.{0,40}interess', titulo, re.I)
                  else 'Manifestação de interesse' if 'manifestação de interesse' in titulo.lower()
                  else 'Pré-inscrição' if 'pré-inscri' in titulo.lower() else 'Seleção')
    return {'url': url, 'status': 'aberta_confirmada', 'titulo': titulo,
            'instituicao': 'Sebrae Startups', 'tipo': modalidade, 'estagio': 'Qualquer',
            'descricao': dados.get('descricao_breve_text', ''), 'requisitos': dados.get('descricao_text', ''),
            'prazo': fim.date().isoformat(), 'prazo_iso': fim.isoformat(),
            'inicio_iso': inicio.isoformat() if inicio else None,
            'evidencia_edicao': edicao.group(0) if edicao else f'Período de inscrição até {fim.date().isoformat()}',
            'evidencia_publico': next((x for x in texto.splitlines() if re.search(r'\bstartups?\b|\bdeep\s*techs?\b|empreendedores? inovadores?|neg[oó]cios inovadores?', x, re.I)), ''),
            'evidencia_prazo': f'data_final_date={int(fim_ms)}',
            'modalidade_inscricao': normalizar(modalidade).replace(' ', '_')}


def data_literal(trecho):
    from cronogramas import datas
    encontradas = datas(trecho)
    return max(encontradas) if encontradas else None


def texto_relevante(texto, limite=30000):
    """Preserva cronogramas no fim de páginas longas sem enviar conteúdo inteiro."""
    if len(texto) <= limite:
        return texto
    linhas = texto.splitlines()
    marcadas = set()
    padrao = re.compile(r'inscri[cç]|inscrev|candidat|submiss|prazo|cronograma|fluxo cont[ií]nuo|\b20\d{2}\b', re.I)
    for i, linha in enumerate(linhas):
        if padrao.search(linha):
            marcadas.add(i)
    recortes = '\n'.join(linhas[i] for i in sorted(marcadas))
    return texto[:5000] + '\n' + recortes[:limite - 5001]


def prazo_da_oportunidade(trecho, titulo):
    """Exige nome distintivo no mesmo trecho do prazo; não usa datas da página inteira."""
    genericos = {'programa', 'edital', 'novo', 'nova', 'chamada', 'selecao', 'para',
                 'startups', 'startup', 'inscricoes', 'abertas', 'primeira', 'de', 'da',
                 'do', 'e', 'a', 'o', 'no', 'na', 'em', 'fluxo', 'continuo', 'open'}
    palavras = [p for p in normalizar(titulo).split()
                if len(p) >= 4 and not p.isdigit() and p not in genericos]
    palavras += [normalizar(p) for p in re.findall(r'\b[A-Z]{3,}\b', titulo)]
    if not palavras:
        return False
    encontrados = set(normalizar(trecho).split())
    return any(p in encontrados for p in palavras)


def validar_oficial(registro, agora, ler=None):
    url = registro['url']
    fonte = registro.get('fonte_primaria_descoberta') or FONTES_OFICIAIS.get(url, url)
    if not oficial(fonte) and fonte == url:
        from fontes_primarias import localizar
        alternativas = localizar(registro, oficial) if ler is None else []
        melhor = None
        for primaria in alternativas:
            candidato = dict(registro, fonte_primaria_descoberta=primaria)
            resultado = validar_oficial(candidato, agora, ler)
            if resultado['status'] in ('aberta_confirmada', 'encerrada'):
                resultado['fonte_oficial'] = primaria
                return resultado
            melhor = resultado
        if melhor:
            melhor['fontes_consultadas'] = alternativas
            return melhor
        return {'url':url, 'titulo':registro.get('titulo',''), 'status':'pendente_fonte_oficial',
                'motivo':'localizar_fonte_primaria'}
    try:
        if ler is None:
            import radar
            ctype, bruto = radar.baixar(fonte)
            if bruto is None:
                raise ValueError('leitura_bloqueada')
            from cronogramas import ler_texto
            texto = texto_relevante(ler_texto(ctype, bruto), radar.MAX_CHARS)
        else:
            texto = ler(fonte)
    except Exception:
        return {'url':url, 'titulo':registro.get('titulo',''), 'status':'pendente_acesso',
                'motivo':'fonte_oficial_indisponivel'}
    titulo = registro.get('dados',{}).get('titulo') or registro.get('titulo','')
    dados_registro = registro.get('dados', {})
    # O extrator separa convite e público. Em chamadas para empresas inovadoras,
    # a palavra "startups" pode aparecer literalmente no trecho da oportunidade
    # e o recorte de público trazer apenas os requisitos societários.
    trechos_publico = [dados_registro.get('trecho_publico', ''),
                       dados_registro.get('trecho_oportunidade', '')]
    publico = next((x for x in trechos_publico
                    if re.search(r'startup|neg[oó]cio inovador|projeto inovador', x, re.I)),
                   dados_registro.get('trecho_publico', ''))
    from cronogramas import prazo_documentado
    cronograma = prazo_documentado(texto, titulo)
    if cronograma and re.search(r'startup|neg[oó]cio inovador|projeto inovador', publico, re.I):
        fim = cronograma['fim']; inicio = cronograma['inicio']
        base = {'url':url, 'titulo':titulo, 'fonte_oficial':fonte,
                'prazo_iso':fim.isoformat(), 'evidencia_prazo':cronograma['evidencia'],
                'metodo':'cronograma_documentado'}
        if fim <= agora:
            return dict(base, status='encerrada')
        dados = registro.get('dados', {})
        return dict(base, status='ainda_nao_aberta' if inicio and inicio > agora else 'aberta_confirmada',
            instituicao=dados.get('instituicao') or urlsplit(fonte).hostname,
            tipo=dados.get('tipo') or 'Seleção', estagio='Qualquer',
            descricao=dados.get('resumo', ''), requisitos=publico,
            prazo=fim.date().isoformat(), inicio_iso=inicio.isoformat() if inicio else None,
            evidencia_edicao=str(fim.year), evidencia_publico=publico,
            modalidade_inscricao='inscricao', sem_data_final=False)
    # Algumas instituições mantêm a página primária no próprio URL descoberto.
    # O catálogo estruturado da FAPEMIG é uma página dedicada à chamada, não uma
    # notícia agregadora; seu cronograma pode separar o nome da chamada da data.
    pagina_dedicada = (url in FONTES_OFICIAIS or
                       '/oportunidades/chamadas-e-editais/' in urlsplit(fonte).path)
    edicao = re.search(r'\b20\d{2}\b', titulo)
    if (not edicao and not pagina_dedicada) or not re.search(r'startup|neg[oó]cio inovador|projeto inovador', publico, re.I):
        return {'url':url, 'titulo':titulo, 'status':'pendente_evidencia',
                'motivo':'edicao_ou_publico_nao_comprovado'}
    trechos = [x.strip() for x in re.split(r'(?<=[.!?])\s+|\n+', texto) if x.strip()]
    # Mapeamentos são páginas oficiais dedicadas à oportunidade. Nelas, o prazo
    # pode estar no cronograma sem repetir o nome do programa na mesma linha.
    candidatos = [(data_literal(x), x) for x in trechos
                  if re.search(r'inscri[cç]|inscrev|candidat|cadast|submiss|prazo', x, re.I)
                  and not re.search(r'\babert[ao]s?\s+a\s+partir\s+de\b', x, re.I)
                  and (pagina_dedicada or prazo_da_oportunidade(x, titulo))]
    # Rótulos de cronograma podem ficar separados da data por tags HTML.
    if prazo_da_oportunidade(texto[:5000], titulo):
        data_numerica = r'\d{1,2}[/-]\d{1,2}[/-]20\d{2}'
        padrao = (r'(?:encerramento\s+(?:das\s+)?inscri[cç][oõ]es|prazo\s+para\s+submiss[aã]o)'
                  r'\s*:?\s*' + data_numerica + r'(?:\s+a\s+' + data_numerica + r')?')
        for m in re.finditer(padrao, texto, re.I):
            candidatos.append((data_literal(m.group(0)), m.group(0)))
    candidatos = [(d,x) for d,x in candidatos if d]
    blocos=[x.strip() for x in texto.split('\n') if x.strip()]
    continuo = next((' '.join(blocos[max(0,i-1):i+1]) for i,x in enumerate(blocos)
                     if prazo_da_oportunidade(' '.join(blocos[max(0,i-1):i+1]), titulo)
                     and re.search(r'inscri[cç].{0,100}fluxo cont[ií]nuo|fluxo cont[ií]nuo.{0,100}inscri[cç]', x, re.I)), None)
    # PDFs e páginas dedicadas podem separar "fluxo contínuo", a abertura das
    # inscrições e a identificação do edital em blocos distintos.
    if not continuo and (pagina_dedicada or prazo_da_oportunidade(texto[:5000], titulo)):
        fluxo = next((x for x in blocos[:80] if re.search(r'fluxo cont[ií]nuo', x, re.I)), None)
        convite = next((x for x in blocos[:120] if re.search(
            r'est[aã]o abertas as inscri[cç]|inscri[cç][aã]o ser[aá]|podem submeter|'
            r'processo de sele[cç][aã]o [ée] cont[ií]nuo|encerramento\s*:\s*n[aã]o se aplica', x, re.I)), None)
        if fluxo and convite:
            continuo = fluxo + ' ' + convite
    if not candidatos and not continuo:
        return {'url':url, 'titulo':titulo, 'status':'pendente_evidencia',
                'motivo':'prazo_literal_com_ano_nao_encontrado'}
    if continuo:
        edicao_continua = edicao
        if not edicao_continua:
            edicao_continua = re.search(
                r'(?:edital(?:\s+n[ºo.]*)?\s*\d+[/-]|abertura\s*:?\s*\d{1,2}[/-]\d{1,2}[/-])(20\d{2})',
                texto, re.I)
        if not edicao_continua:
            return {'url':url, 'titulo':titulo, 'status':'pendente_evidencia',
                    'motivo':'edicao_nao_comprovada'}
        ano_continuo = edicao_continua.group(1) if edicao_continua.lastindex else edicao_continua.group(0)
        modalidade='Pré-incubação' if 'pré-incuba' in titulo.lower() else 'Inscrição'
        return {'url':url,'fonte_oficial':fonte,'status':'aberta_confirmada','titulo':titulo,'instituicao':urlsplit(fonte).hostname,
                'tipo':modalidade,'estagio':'Qualquer','descricao':registro.get('dados',{}).get('resumo',''),
                'requisitos':publico,'prazo':None,'prazo_iso':None,'inicio_iso':None,
                'evidencia_edicao':ano_continuo,
                'evidencia_publico':publico,'evidencia_prazo':continuo,
                'modalidade_inscricao':'fluxo_continuo','sem_data_final':True}
    fim, evidencia = max(candidatos, key=lambda x:x[0])
    evidencia_edicao = edicao.group(0) if edicao else str(fim.year)
    if fim <= agora:
        return {'url':url,'titulo':titulo,'status':'encerrada','prazo_iso':fim.isoformat(),'evidencia_prazo':evidencia}
    modalidade=('Aceleração' if dados_registro.get('tipo') == 'Aceleração' else
                'Pré-inscrição' if 'pré-inscri' in titulo.lower() else
                'Manifestação de interesse' if 'manifestação de interesse' in titulo.lower() else
                'Pré-incubação' if 'pré-incuba' in titulo.lower() else 'Seleção')
    return {'url':url,'fonte_oficial':fonte,'status':'aberta_confirmada','titulo':titulo,'instituicao':urlsplit(fonte).hostname,
            'tipo':modalidade,'estagio':'Qualquer','descricao':registro.get('dados',{}).get('resumo',''),
            'requisitos':publico,'prazo':fim.date().isoformat(),'prazo_iso':fim.isoformat(),'inicio_iso':None,
            'evidencia_edicao':evidencia_edicao,
            'evidencia_publico':publico,'evidencia_prazo':evidencia,
            'modalidade_inscricao':normalizar(modalidade).replace(' ','_'),'sem_data_final':False}


def deduplicar(itens):
    unicos = {}
    for e in itens:
        chave = (normalizar(e['titulo']), normalizar(e['instituicao']))
        atual = unicos.get(chave)
        # Fluxo contínuo não tem prazo_iso; ainda assim pode ser deduplicado.
        if not atual or (e.get('prazo_iso') or '') > (atual.get('prazo_iso') or ''):
            unicos[chave] = e
    return list(unicos.values())


def atualizar_acompanhamento(itens, abertas, agora, fila=None, ia=None):
    """Mantém o progresso da vigência visível no painel já publicado."""
    caminho = Path('docs/busca.json')
    painel = json.loads(caminho.read_text()) if caminho.exists() else {}
    contagem = {}
    for item in itens:
        status = item.get('status', 'desconhecido')
        contagem[status] = contagem.get(status, 0) + 1
    painel['vigencia'] = {
        'atualizado_em': agora.isoformat(),
        'examinadas': len(itens),
        'abertas_publicadas': len(abertas),
        'status': contagem,
        'resultados': [
            {'titulo': item.get('titulo', ''), 'url': item['url'],
             'status': item.get('status'), 'motivo': item.get('motivo', '')}
            for item in itens
        ],
        'pendentes': [
            {'titulo': item.get('titulo', ''), 'url': item['url'],
             'status': item.get('status'), 'motivo': item.get('motivo', '')}
            for item in itens if item.get('status', '').startswith('pendente_')
        ],
    }
    if fila is not None:painel['vigencia']['fila_prioritaria'] = fila
    if ia is not None:painel['vigencia']['ia'] = ia
    caminho.write_text(json.dumps(painel, ensure_ascii=False, indent=2) + '\n')


def verificacao_atual(item, agora):
    try:
        verificado = datetime.fromisoformat(item['verificado_em'])
        idade = agora - verificado
    except (KeyError, TypeError, ValueError):
        return False
    limite = timedelta(hours=24 if item.get('sem_data_final') else 48)
    return timedelta(0) <= idade < limite


def exportar_abertas(validadas, agora):
    saida = []
    for e in deduplicar([x for x in validadas if x.get('status') == 'aberta_confirmada']):
        continuo = e.get('sem_data_final', False)
        fim = None if continuo else datetime.fromisoformat(e['prazo_iso'])
        if fim and fim <= agora:
            continue
        inicio = datetime.fromisoformat(e['inicio_iso']) if e.get('inicio_iso') else None
        if (inicio and inicio > agora) or not verificacao_atual(e, agora):
            continue
        verificado = datetime.fromisoformat(e['verificado_em'])
        validade = verificado + timedelta(hours=24 if continuo else 48)
        if fim:
            validade = min(validade, fim)
        saida.append({'t': e['titulo'], 'o': e['instituicao'], 'tipo': e['tipo'],
            'est': e['estagio'], 'v': 0, 'prazo': e['prazo'],
            'd': None if continuo else (fim.date() - agora.date()).days, 'desc': e['descricao'], 'link': e.get('fonte_oficial', e['url']),
            'n': 1, 'r': 0, 'revisar': 0, 'status': e['modalidade_inscricao'] + '_aberta',
            'requisitos': e['requisitos'], 'verificado_em': e['verificado_em'],
            'validado_automaticamente': not e.get('metodo', '').startswith('revisao_manual'),
            'validado_manualmente': e.get('metodo', '').startswith('revisao_manual'), 'prazo_iso': e['prazo_iso'],
            'sem_data_final': continuo, 'verificacao_valida_ate': validade.isoformat(),
            'evidencia_edicao': e['evidencia_edicao'],
            'evidencia_publico': e['evidencia_publico'], 'evidencia_prazo': e['evidencia_prazo']})
    return saida


def main():
    import radar
    from leitura_cache import leitor_cache
    from leitor_navegador import leitor_com_navegador
    leitor = leitor_com_navegador(leitor_cache(radar.baixar), radar.permitido)
    radar.baixar = leitor
    agora = datetime.now(FUSO)
    qualidade = json.loads(Path('data/revisao-qualidade.json').read_text())
    if not qualidade.get('avancar_vigencia'):
        raise SystemExit('Gate de qualidade ainda não liberou vigência')
    conteudo = json.loads(Path('data/oportunidades-conteudo.json').read_text())
    confirmadas = [e for e in conteudo['itens'] if e.get('status') == 'confirmada_no_conteudo'
                   or ('programas.sebraestartups.com.br/in/' in e['url'])]
    # Nas páginas estruturadas, a própria validação confere programa, público e prazo;
    # não depende da cota de IA para ler campos oficiais.
    anteriores_path = Path('data/oportunidades-vigencia.json')
    historico = json.loads(anteriores_path.read_text()) if anteriores_path.exists() else {}
    # Invalida resultados antigos que aceitavam um ano histórico como edição atual.
    anteriores = historico.get('itens', []) if historico.get('versao') in ('vigencia-v11', 'vigencia-v12') else []
    feitos = {e['url']: e for e in anteriores}
    pendentes = [e for e in confirmadas if e['url'] not in feitos or
                 (feitos[e['url']].get('status') == 'aberta_confirmada' and
                  (not verificacao_atual(feitos[e['url']], agora) or feitos[e['url']].get('metodo_leitura') != 'cronogramas-v6')) or
                 (feitos[e['url']].get('metodo', '').startswith('revisao_manual') and feitos[e['url']].get('metodo_leitura') != 'cronogramas-v6') or
                 feitos[e['url']].get('status') in ('pendente_metodo','pendente_acesso') or
                 (feitos[e['url']].get('status') == 'pendente_fonte_oficial' and
                  (feitos[e['url']].get('metodo_fontes') != 'links-v2' or
                   not verificacao_atual(feitos[e['url']], agora))) or
                 (feitos[e['url']].get('status', '').startswith('pendente_') and
                  (e['url'] in FONTES_OFICIAIS or feitos[e['url']].get('metodo_fontes') != 'links-v2' or feitos[e['url']].get('metodo_leitura') != 'cronogramas-v6' or not verificacao_atual(feitos[e['url']], agora)))]
    # Um commit de dados não dispara novamente este workflow. O lote precisa cobrir
    # todas as confirmações restantes sem depender de uma segunda execução manual.
    lote = sorted(pendentes, key=lambda e: (e['url'] != MERCOPAR,
                       'programas.sebraestartups.com.br/in/' not in e['url'],
                       not oficial(e['url'])))[:80]
    def validar(e):
        resultado = (validar_sebrae(e, agora) if 'programas.sebraestartups.com.br/in/' in e['url']
                     else validar_oficial(e, agora))
        resultado.setdefault('titulo', e.get('titulo', ''))
        resultado['metodo_fontes'] = 'links-v2'
        resultado['metodo_leitura'] = 'cronogramas-v6'
        resultado['verificado_em'] = datetime.now(FUSO).isoformat()
        print(f"{resultado['status']}: {e['url']}", flush=True)
        return resultado
    with ThreadPoolExecutor(max_workers=4) as pool:
        for resultado in pool.map(validar, lote):
            antigo = feitos.get(resultado['url'], {})
            if antigo.get('metodo', '').startswith('revisao_manual') and resultado['status'].startswith('pendente_'):
                antigo['metodo_leitura'] = 'cronogramas-v6'
                antigo['resultado_releitura_automatica'] = resultado.get('motivo')
            else:
                feitos[resultado['url']] = resultado
    # IA sequencial e limitada: somente os casos não resolvidos por regras.
    from vigencia_ia import Verificador, documentos
    assistente = Verificador()
    if os.getenv('GEMINI_API_KEY'):
        candidatos_ia = [e for e in confirmadas if feitos.get(e['url'], {}).get('status') in
                         ('pendente_evidencia', 'pendente_fonte_oficial')]
        # Casos inéditos primeiro; exemplos já revisados não monopolizam a cota.
        candidatos_ia.sort(key=lambda e: (bool(feitos[e['url']].get('ia_tentada_em')),
                                             feitos[e['url']].get('ia_tentada_em', ''), not oficial(e['url'])))
        for e in candidatos_ia:
            if assistente.parada or assistente.usadas >= assistente.limite:
                break
            anterior = feitos[e['url']]
            tentativa = anterior.get('ia_tentada_em')
            if anterior.get('ia_metodo') == 'gemini-v7' and tentativa and (agora - datetime.fromisoformat(tentativa)) < timedelta(hours=24):
                continue
            docs = documentos(dict(e, fonte_primaria_descoberta=FONTES_OFICIAIS.get(e['url'], e['url'])), oficial)
            resultado = assistente.verificar(e, docs, agora)
            anterior['ia_tentada_em'] = datetime.now(FUSO).isoformat()
            anterior['ia_metodo'] = 'gemini-v7'
            anterior['motivo_ia'] = assistente.parada or assistente.last_reason or ('sem_documentos' if not docs else 'evidencia_insuficiente')
            if assistente.parada:
                anterior.pop('ia_tentada_em', None)
                break
            if resultado:
                resultado['verificado_em'] = datetime.now(FUSO).isoformat()
                resultado['ia_tentada_em'] = anterior['ia_tentada_em']
                resultado['ia_metodo'] = 'gemini-v7'
                feitos[e['url']] = resultado
                print(f"IA: {resultado['status']}: {e['url']}", flush=True)
    print(f'IA: {assistente.usadas} chamadas; parada={assistente.parada}', flush=True)
    agora = datetime.now(FUSO)
    itens = list(feitos.values())
    relatorio = {'versao':'vigencia-v12', 'atualizado_em':agora.isoformat(), 'leitura_navegador': leitor.estatisticas, 'ia': {'chamadas': assistente.usadas, 'falhas_temporarias': assistente.erros, 'limite': assistente.limite, 'parada': assistente.parada, 'pendencias_restantes': sum(x.get('status', '').startswith('pendente_') for x in itens), 'casos_com_tentativa_ia': sum(bool(x.get('ia_tentada_em')) for x in itens), 'resolvidas_automaticamente': sum(x.get('status') in ('aberta_confirmada','encerrada') and not x.get('metodo','').startswith('revisao_manual') for x in itens), 'revisoes_manuais': sum(x.get('metodo','').startswith('revisao_manual') for x in itens)}, 'itens':itens}
    anteriores_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2)+'\n')
    fila_path = Path('data/fila-vigencia-inicial.json')
    fila_urls = json.loads(fila_path.read_text()).get('urls', []) if fila_path.exists() else []
    resolvidas = [feitos[u] for u in fila_urls if u in feitos and feitos[u].get('status') in ('aberta_confirmada','encerrada','ainda_nao_aberta')]
    fila = {'total_inicial': len(fila_urls), 'resolvidas': len(resolvidas),
            'resolvidas_automaticamente': sum(not x.get('metodo','').startswith('revisao_manual') for x in resolvidas),
            'revisoes_manuais': sum(x.get('metodo','').startswith('revisao_manual') for x in resolvidas),
            'pendentes': len(fila_urls)-len(resolvidas)}
    relatorio['fila_prioritaria'] = fila
    anteriores_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2)+'\n')
    abertas = exportar_abertas(itens, agora)
    Path('docs/editais.json').write_text(json.dumps(abertas, ensure_ascii=False, indent=2)+'\n')
    atualizar_acompanhamento(itens, abertas, agora, fila, relatorio['ia'])
    print(f'{len(lote)} examinadas; {len(abertas)} abertas confirmadas publicadas')


if __name__ == '__main__':
    main()
