"""Valida edição, público e prazo; publica somente oportunidades abertas comprovadas."""
import json
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

FUSO = ZoneInfo('America/Sao_Paulo')
MERCOPAR = 'https://programas.sebraestartups.com.br/in/1783963246760x826977266273542100'
FONTES_OFICIAIS = {
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
MESES = {'janeiro':1,'fevereiro':2,'marco':3,'abril':4,'maio':5,'junho':6,
         'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12}


def normalizar(s):
    s = ''.join(c for c in unicodedata.normalize('NFKD', str(s).lower())
                if not unicodedata.combining(c))
    return re.sub(r'\W+', ' ', s).strip()


def oficial(url):
    host = (urlsplit(url).hostname or '').lower()
    return (host.endswith('.gov.br') or host.endswith('.gov.pt') or
            host.endswith('.edu.br') or host.endswith('.org.br') or
            any(x in host for x in ('sebrae', 'fapemig', 'fapesc', 'finep', 'google.com',
                'grupoboticario.com.br', 'natura.com.br', 'randoncorp.com', 'startupbrasil.org.br',
                'cbamazonia.org')))


def dados_sebrae(url, abrir=urlopen):
    p = urlsplit(url)
    if p.hostname != 'programas.sebraestartups.com.br' or not p.path.startswith('/in/'):
        return None
    endpoint = f'{p.scheme}://{p.netloc}/api/1.1/init/data?location={quote(url, safe="")}'
    req = Request(endpoint, headers={'User-Agent': 'RadarStartups/1.0'})
    with abrir(req, timeout=30) as resposta:
        registros = json.load(resposta)
    for registro in registros if isinstance(registros, list) else []:
        if registro.get('id') == p.path.rsplit('/', 1)[-1]:
            return registro.get('data', {})
    return None


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
    publico = bool(re.search(r'\bstartups?\b', titulo + ' ' + dados.get('descricao_text', ''), re.I))
    edicao = re.search(r'\b20\d{2}\b', titulo)
    if not (ativo and publico and edicao and isinstance(fim_ms, (int, float))):
        return {'url': url, 'status': 'pendente_evidencia',
                'motivo': 'edicao_publico_atividade_ou_prazo_nao_comprovado'}
    fim = datetime.fromtimestamp(fim_ms / 1000, FUSO)
    inicio = datetime.fromtimestamp(inicio_ms / 1000, FUSO) if isinstance(inicio_ms, (int, float)) else None
    if fim <= agora:
        return {'url': url, 'status': 'encerrada', 'prazo_iso': fim.isoformat(),
                'evidencia_prazo': f'data_final_date={int(fim_ms)}'}
    modalidade = ('Manifestação de interesse' if 'manifestação de interesse' in titulo.lower()
                  else 'Pré-inscrição' if 'pré-inscri' in titulo.lower() else 'Seleção')
    return {'url': url, 'status': 'aberta_confirmada', 'titulo': titulo,
            'instituicao': 'Sebrae Startups', 'tipo': modalidade, 'estagio': 'Qualquer',
            'descricao': dados.get('descricao_breve_text', ''), 'requisitos': dados.get('descricao_text', ''),
            'prazo': fim.date().isoformat(), 'prazo_iso': fim.isoformat(),
            'inicio_iso': inicio.isoformat() if inicio else None,
            'evidencia_edicao': edicao.group(0),
            'evidencia_publico': registro.get('dados', {}).get('trecho_publico', ''),
            'evidencia_prazo': f'data_final_date={int(fim_ms)}',
            'modalidade_inscricao': normalizar(modalidade).replace(' ', '_')}


def data_literal(trecho):
    limpo = ''.join(c for c in unicodedata.normalize('NFKD', str(trecho).lower())
                    if not unicodedata.combining(c))
    datas = []
    for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b', limpo):
        dia, mes, ano = map(int, m.groups())
        try: datas.append(datetime(ano, mes, dia, 23, 59, 59, tzinfo=FUSO))
        except ValueError: pass
    for m in re.finditer(r'\b(\d{1,2}) de (' + '|'.join(MESES) + r') de (20\d{2})\b', limpo):
        try: datas.append(datetime(int(m.group(3)), MESES[m.group(2)], int(m.group(1)), 23, 59, 59, tzinfo=FUSO))
        except ValueError: pass
    return max(datas) if datas else None


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
                 'do', 'e', 'a', 'o', 'no', 'na', 'em'}
    palavras = [p for p in normalizar(titulo).split()
                if len(p) >= 4 and not p.isdigit() and p not in genericos]
    if not palavras:
        return False
    encontrados = set(normalizar(trecho).split())
    return any(p in encontrados for p in palavras)


def validar_oficial(registro, agora, ler=None):
    url = registro['url']
    fonte = FONTES_OFICIAIS.get(url, url)
    if not oficial(fonte) and fonte == url:
        return {'url':url, 'titulo':registro.get('titulo',''), 'status':'pendente_fonte_oficial',
                'motivo':'localizar_fonte_primaria'}
    try:
        if ler is None:
            import radar
            ctype, bruto = radar.baixar(fonte)
            if bruto is None:
                raise ValueError('leitura_bloqueada')
            texto = texto_relevante(radar.para_texto(ctype, bruto), radar.MAX_CHARS)
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
    # Algumas instituições mantêm a página primária no próprio URL descoberto.
    # O catálogo estruturado da FAPEMIG é uma página dedicada à chamada, não uma
    # notícia agregadora; seu cronograma pode separar o nome da chamada da data.
    pagina_dedicada = (fonte != url or
                       '/oportunidades/chamadas-e-editais/' in urlsplit(fonte).path)
    edicao = re.search(r'\b20\d{2}\b', titulo)
    if (not edicao and not pagina_dedicada) or not re.search(r'startup|neg[oó]cio inovador|projeto inovador', publico, re.I):
        return {'url':url, 'titulo':titulo, 'status':'pendente_evidencia',
                'motivo':'edicao_ou_publico_nao_comprovado'}
    trechos = [x.strip() for x in re.split(r'(?<=[.!?])\s+|\n+', texto) if x.strip()]
    # Mapeamentos são páginas oficiais dedicadas à oportunidade. Nelas, o prazo
    # pode estar no cronograma sem repetir o nome do programa na mesma linha.
    candidatos = [(data_literal(x), x) for x in trechos
                  if re.search(r'inscri[cç]|inscrev|candidat|submiss|prazo', x, re.I)
                  and not re.search(r'\babert[ao]s?\s+a\s+partir\s+de\b', x, re.I)
                  and (pagina_dedicada or prazo_da_oportunidade(x, titulo))]
    candidatos = [(d,x) for d,x in candidatos if d]
    continuo = next((x for x in trechos if prazo_da_oportunidade(x, titulo) and re.search(r'inscri[cç].{0,100}fluxo cont[ií]nuo|fluxo cont[ií]nuo.{0,100}inscri[cç]', x, re.I)), None)
    if not candidatos and not continuo:
        return {'url':url, 'titulo':titulo, 'status':'pendente_evidencia',
                'motivo':'prazo_literal_com_ano_nao_encontrado'}
    if continuo:
        if not edicao:
            return {'url':url, 'titulo':titulo, 'status':'pendente_evidencia',
                    'motivo':'edicao_nao_comprovada'}
        modalidade='Pré-incubação' if 'pré-incuba' in titulo.lower() else 'Inscrição'
        return {'url':url,'fonte_oficial':fonte,'status':'aberta_confirmada','titulo':titulo,'instituicao':urlsplit(fonte).hostname,
                'tipo':modalidade,'estagio':'Qualquer','descricao':registro.get('dados',{}).get('resumo',''),
                'requisitos':publico,'prazo':None,'prazo_iso':None,'inicio_iso':None,
                'evidencia_edicao':edicao.group(0),
                'evidencia_publico':publico,'evidencia_prazo':continuo,
                'modalidade_inscricao':'fluxo_continuo','sem_data_final':True}
    fim, evidencia = max(candidatos, key=lambda x:x[0])
    evidencia_edicao = edicao.group(0) if edicao else str(fim.year)
    if fim <= agora:
        return {'url':url,'titulo':titulo,'status':'encerrada','prazo_iso':fim.isoformat(),'evidencia_prazo':evidencia}
    modalidade=('Pré-inscrição' if 'pré-inscri' in titulo.lower() else
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


def atualizar_acompanhamento(itens, abertas, agora):
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
    caminho.write_text(json.dumps(painel, ensure_ascii=False, indent=2) + '\n')


def exportar_abertas(validadas, agora):
    saida = []
    for e in deduplicar([x for x in validadas if x.get('status') == 'aberta_confirmada']):
        continuo = e.get('sem_data_final', False)
        fim = None if continuo else datetime.fromisoformat(e['prazo_iso'])
        saida.append({'t': e['titulo'], 'o': e['instituicao'], 'tipo': e['tipo'],
            'est': e['estagio'], 'v': 0, 'prazo': e['prazo'],
            'd': None if continuo else (fim.date() - agora.date()).days, 'desc': e['descricao'], 'link': e.get('fonte_oficial', e['url']),
            'n': 1, 'r': 0, 'revisar': 0, 'status': e['modalidade_inscricao'] + '_aberta',
            'requisitos': e['requisitos'], 'verificado_em': agora.isoformat(),
            'validado_automaticamente': True, 'prazo_iso': e['prazo_iso'],
            'sem_data_final': continuo, 'verificacao_valida_ate': (agora + timedelta(hours=48)).isoformat(),
            'evidencia_edicao': e['evidencia_edicao'],
            'evidencia_publico': e['evidencia_publico'], 'evidencia_prazo': e['evidencia_prazo']})
    return saida


def main():
    agora = datetime.now(FUSO)
    qualidade = json.loads(Path('data/revisao-qualidade.json').read_text())
    if not qualidade.get('avancar_vigencia'):
        raise SystemExit('Gate de qualidade ainda não liberou vigência')
    conteudo = json.loads(Path('data/oportunidades-conteudo.json').read_text())
    confirmadas = [e for e in conteudo['itens'] if e.get('status') == 'confirmada_no_conteudo']
    anteriores_path = Path('data/oportunidades-vigencia.json')
    historico = json.loads(anteriores_path.read_text()) if anteriores_path.exists() else {}
    # Invalida resultados antigos que aceitavam um ano histórico como edição atual.
    anteriores = historico.get('itens', []) if historico.get('versao') == 'vigencia-v10' else []
    feitos = {e['url']: e for e in anteriores}
    pendentes = [e for e in confirmadas if e['url'] not in feitos or
                 feitos[e['url']].get('status') in ('pendente_metodo','pendente_acesso') or
                 (feitos[e['url']].get('status', '').startswith('pendente_') and
                  e['url'] in FONTES_OFICIAIS)]
    # Um commit de dados não dispara novamente este workflow. O lote precisa cobrir
    # todas as confirmações restantes sem depender de uma segunda execução manual.
    lote = sorted(pendentes, key=lambda e: (e['url'] != MERCOPAR, not oficial(e['url'])))[:60]
    for e in lote:
        feitos[e['url']] = (validar_sebrae(e, agora) if 'programas.sebraestartups.com.br/in/' in e['url']
                            else validar_oficial(e, agora))
    itens = list(feitos.values())
    relatorio = {'versao':'vigencia-v10', 'atualizado_em':agora.isoformat(), 'itens':itens}
    anteriores_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2)+'\n')
    abertas = exportar_abertas(itens, agora)
    Path('docs/editais.json').write_text(json.dumps(abertas, ensure_ascii=False, indent=2)+'\n')
    atualizar_acompanhamento(itens, abertas, agora)
    print(f'{len(lote)} examinadas; {len(abertas)} abertas confirmadas publicadas')


if __name__ == '__main__':
    main()
