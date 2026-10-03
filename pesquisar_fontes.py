"""Pesquisa limitada de documentos faltantes, separada da interpretação da vigência."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from fontes_primarias import palavras
from estado_pipeline import salvar_json


def candidatos_compativeis(registro, resultados, oficial):
    titulo = registro.get('dados', {}).get('titulo') or registro.get('titulo', '')
    termos = palavras(titulo)
    anos = set(re.findall(r'\b20\d{2}\b', titulo))
    saida = []
    for resultado in resultados:
        url = resultado.get('url', '')
        if not oficial(url): continue
        texto = resultado.get('title', '') + ' ' + resultado.get('content', '')
        anos_alvo = set(re.findall(r'\b20\d{2}\b', resultado.get('title', '')))
        if anos and anos_alvo and not anos & anos_alvo: continue
        comuns = termos & palavras(texto + ' ' + urlsplit(url).path)
        if len(comuns) < min(2, len(termos)) or not termos or len(comuns) / len(termos) < .5:
            continue
        if not re.search(r'edital|inscri|apply|candidat|program|chamada|acelera|incuba', texto, re.I):
            continue
        if url not in saida: saida.append(url)
    return saida[:3]


def buscar(consulta, chave):
    import requests
    with requests.post('https://api.tavily.com/search',
                       headers={'Authorization': 'Bearer ' + chave},
                       json={'query': consulta, 'max_results': 5, 'search_depth': 'basic'},
                       timeout=(10, 30)) as resposta:
        resposta.raise_for_status()
        return resposta.json().get('results', [])


def executar(limite=4, pesquisar=None, agora=None):
    from validar_vigencia import oficial
    agora = agora or datetime.now(timezone.utc)
    chave = os.getenv('TAVILY_API_KEY')
    if not chave and pesquisar is None:
        return {'consultas': 0, 'fontes_encontradas': 0, 'motivo': 'busca_sem_credencial'}
    pesquisar = pesquisar or (lambda q: buscar(q, chave))
    def carregar(path, padrao):
        try: return json.loads(Path(path).read_text())
        except (OSError, ValueError): return padrao
    cache = carregar('data/estado-pesquisa-fontes.json', {})
    try:
        if datetime.fromisoformat(cache.get('__pausa__', '')) > agora:
            return {'consultas': 0, 'fontes_encontradas': 0, 'motivo': 'busca_cota_em_pausa'}
    except ValueError: pass
    vigencia = carregar('data/oportunidades-vigencia.json', {'itens': []})
    conteudo = {x['url']: x for x in carregar('data/oportunidades-conteudo.json', {'itens': []})['itens']}
    mappings = carregar('data/fontes-primarias-descobertas.json', {})
    # Sem documentos e falha de acesso precisam de busca, não de repetir o prompt.
    fila = [x for x in vigencia['itens'] if x.get('status') in ('pendente_fonte_oficial', 'pendente_acesso')
            or x.get('motivo_ia') == 'sem_documentos']
    fila.sort(key=lambda x: cache.get(x['url'], {}).get('em', ''))
    consultas = encontradas = 0
    motivo = None
    for item in fila:
        if consultas >= limite: break
        anterior = cache.get(item['url'], {})
        try:
            if datetime.fromisoformat(anterior['proxima_tentativa']) > agora: continue
        except (KeyError, ValueError): pass
        registro = conteudo.get(item['url'], item)
        # Não pesquisar registros cujo conteúdo foi explicitamente descartado.
        if registro.get('status') in ('fora_escopo', 'nao_confirmada_no_texto'): continue
        titulo = registro.get('dados', {}).get('titulo') or registro.get('titulo', '')
        consultas += 1
        entrada = {'em': agora.isoformat(), 'proxima_tentativa': (agora + timedelta(days=1)).isoformat()}
        try:
            urls = candidatos_compativeis(registro, pesquisar(titulo + ' edital inscrições fonte oficial'), oficial)
            entrada['fontes'] = urls
            if urls:
                mappings[item['url']] = urls[0]
                encontradas += 1
        except Exception as erro:
            resposta = getattr(erro, 'response', None)
            codigo = resposta.status_code if resposta is not None else None
            entrada['erro'] = 'http_' + str(codigo) if codigo else type(erro).__name__
            if codigo in (402, 429, 432):
                cache['__pausa__'] = (agora + timedelta(hours=6)).isoformat()
                motivo = 'busca_cota_em_pausa'
            else:
                entrada['proxima_tentativa'] = (agora + timedelta(minutes=15)).isoformat()
        cache[item['url']] = entrada
        salvar_json('data/estado-pesquisa-fontes.json', cache)
        salvar_json('data/fontes-primarias-descobertas.json', mappings)
        if motivo: break
    return {'consultas': consultas, 'fontes_encontradas': encontradas, 'motivo': motivo}
