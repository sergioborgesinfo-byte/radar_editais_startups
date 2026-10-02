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


def normalizar(s):
    s = ''.join(c for c in unicodedata.normalize('NFKD', str(s).lower())
                if not unicodedata.combining(c))
    return re.sub(r'\W+', ' ', s).strip()


def oficial(url):
    host = (urlsplit(url).hostname or '').lower()
    return (host.endswith('.gov.br') or host.endswith('.edu.br') or host.endswith('.org.br') or
            any(x in host for x in ('sebrae', 'fapemig', 'fapesc', 'finep', 'google.com',
                'grupoboticario.com.br', 'natura.com.br', 'randoncorp.com', 'startupbrasil.org.br')))


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


def deduplicar(itens):
    unicos = {}
    for e in itens:
        chave = (normalizar(e['titulo']), normalizar(e['instituicao']))
        atual = unicos.get(chave)
        if not atual or e['prazo_iso'] > atual['prazo_iso']:
            unicos[chave] = e
    return list(unicos.values())


def exportar_abertas(validadas, agora):
    saida = []
    for e in deduplicar([x for x in validadas if x.get('status') == 'aberta_confirmada']):
        fim = datetime.fromisoformat(e['prazo_iso'])
        saida.append({'t': e['titulo'], 'o': e['instituicao'], 'tipo': e['tipo'],
            'est': e['estagio'], 'v': 0, 'prazo': e['prazo'],
            'd': (fim.date() - agora.date()).days, 'desc': e['descricao'], 'link': e['url'],
            'n': 1, 'r': 0, 'revisar': 0, 'status': e['modalidade_inscricao'] + '_aberta',
            'requisitos': e['requisitos'], 'verificado_em': agora.isoformat(),
            'validado_automaticamente': True, 'prazo_iso': e['prazo_iso'],
            'sem_data_final': False, 'verificacao_valida_ate': (agora + timedelta(hours=48)).isoformat(),
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
    anteriores = json.loads(anteriores_path.read_text()).get('itens', []) if anteriores_path.exists() else []
    feitos = {e['url']: e for e in anteriores}
    pendentes = [e for e in confirmadas if e['url'] not in feitos]
    lote = sorted(pendentes, key=lambda e: (e['url'] != MERCOPAR, not oficial(e['url'])))[:20]
    for e in lote:
        feitos[e['url']] = (validar_sebrae(e, agora) if 'programas.sebraestartups.com.br/in/' in e['url']
                            else {'url': e['url'], 'titulo': e.get('titulo', ''),
                                  'status': 'pendente_fonte_oficial' if not oficial(e['url']) else 'pendente_metodo',
                                  'motivo': 'localizar_fonte_primaria' if not oficial(e['url']) else 'extrator_oficial_a_implementar'})
    itens = list(feitos.values())
    relatorio = {'versao':'vigencia-v1', 'atualizado_em':agora.isoformat(), 'itens':itens}
    anteriores_path.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2)+'\n')
    Path('docs/editais.json').write_text(json.dumps(exportar_abertas(itens, agora), ensure_ascii=False, indent=2)+'\n')
    print(f'{len(lote)} examinadas; {len(exportar_abertas(itens, agora))} abertas confirmadas publicadas')


if __name__ == '__main__':
    main()
