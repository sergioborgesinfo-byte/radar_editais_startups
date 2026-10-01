"""Descoberta ampla: guarda candidatos, sem afirmar que estão abertos."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import requests


def normalizar_url(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        return None
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/') or '/', p.query, ''))


def descobrir():
    cfg = json.loads(Path('sources.json').read_text(encoding='utf-8'))
    chave = os.environ['TAVILY_API_KEY']
    destino = Path('data/oportunidades-descobertas.json')
    anteriores = json.loads(destino.read_text()) if destino.exists() else {'oportunidades': []}
    itens = {e['url']: e for e in anteriores['oportunidades']}
    inicio = datetime.now(timezone.utc)
    for fonte in cfg['descoberta'].get('urls', []):
        url = normalizar_url(fonte['url'])
        if url:
            itens.setdefault(url, {'url': url, 'titulo': fonte['titulo'], 'resumo_busca': fonte.get('resumo', ''),
                'descoberto_em': inicio.isoformat(), 'encontrado_em': inicio.isoformat(),
                'consultas': ['Fonte indicada'], 'situacao': 'aguarda_verificacao'})
    consultas = list(dict.fromkeys(cfg['descoberta']['consultas']))
    erros = []
    encontrados = set()
    for modelo in consultas:
        consulta = modelo.replace('{ano}', str(inicio.year))
        try:
            for tentativa in range(3):
                with requests.post('https://api.tavily.com/search',
                    headers={'Authorization': 'Bearer ' + chave},
                    json={'query': consulta, 'max_results': 10, 'search_depth': 'basic'},
                    timeout=(10, 45)) as resposta:
                    if resposta.status_code in (429, 500, 502, 503, 504) and tentativa < 2:
                        time.sleep(5 * (tentativa + 1))
                        continue
                    resposta.raise_for_status()
                    resultados = resposta.json().get('results', [])
                    break
            for resultado in resultados:
                url = normalizar_url(resultado.get('url', ''))
                if not url:
                    continue
                encontrados.add(url)
                item = itens.setdefault(url, {'url': url, 'descoberto_em': inicio.isoformat(), 'consultas': []})
                item.update(titulo=resultado.get('title', ''), resumo_busca=resultado.get('content', ''),
                            encontrado_em=inicio.isoformat(), situacao='aguarda_verificacao')
                if consulta not in item['consultas']:
                    item['consultas'].append(consulta)
            print(f'Descoberta: {consulta}: {len(resultados)} resultados', flush=True)
        except requests.RequestException as erro:
            # Não imprime cabeçalhos nem a chave.
            status = erro.response.status_code if erro.response is not None else None
            erros.append({'consulta': consulta, 'tipo': type(erro).__name__, 'http': status})
            print(f'Consulta não concluída: {consulta} ({type(erro).__name__}, HTTP {status})', flush=True)
    relatorio = {'executado_em': inicio.isoformat(), 'consultas_previstas': len(consultas),
                 'consultas_concluidas': len(consultas) - len(erros), 'urls_nesta_execucao': len(encontrados),
                 'erros': erros, 'oportunidades': sorted(itens.values(), key=lambda e: e['url'])}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    resumo = (f'## Descoberta de oportunidades\n\n'
              f'{len(consultas)-len(erros)}/{len(consultas)} pesquisas concluídas. '
              f'{len(encontrados)} URLs distintas nesta execução; {len(itens)} no histórico.\n\n'
              'São candidatos: inscrições e elegibilidade ainda precisam de confirmação.\n')
    print(resumo)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(resumo)
    if not encontrados:
        raise SystemExit('Nenhum candidato encontrado: confira o relatório de falhas.')


if __name__ == '__main__':
    descobrir()
