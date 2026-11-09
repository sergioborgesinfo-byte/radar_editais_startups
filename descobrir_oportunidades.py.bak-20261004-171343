"""Descoberta ampla: guarda candidatos, sem afirmar que estão abertos."""
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from estado_pipeline import salvar_json
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
    cursor = anteriores.get('cursor_consultas', 0) % max(1, len(consultas))
    limite = min(int(os.getenv('DESCOBERTA_LIMITE', '24')), len(consultas))
    lote = (consultas[cursor:] + consultas[:cursor])[:limite]
    pausa_ate = anteriores.get('pausa_ate')
    estado_busca = Path('data/estado-pesquisa-fontes.json')
    if estado_busca.exists():
        pausa_ate = max(pausa_ate or '', json.loads(estado_busca.read_text()).get('__pausa__', ''))
    em_pausa = False
    try:
        em_pausa = datetime.fromisoformat(pausa_ate) > inicio
    except (ValueError, TypeError):
        pass
    if em_pausa:
        lote = []
    executadas = 0
    for modelo in lote:
        executadas += 1
        consulta = modelo.replace('{ano}', str(inicio.year))
        try:
            for tentativa in range(3):
                with requests.post('https://api.tavily.com/search',
                    headers={'Authorization': 'Bearer ' + chave},
                    json={'query': consulta, 'max_results': 10, 'search_depth': 'basic'},
                    timeout=(10, 45)) as resposta:
                    if resposta.status_code in (500, 502, 503, 504) and tentativa < 2:
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
            if status in (402, 429, 432):
                pausa_ate = (inicio + timedelta(hours=6)).isoformat()
                em_pausa = True
            if status in (401, 402, 403, 429, 432): break
    relatorio = {'executado_em': inicio.isoformat(), 'consultas_previstas': len(lote),
                 'status': 'pausada_por_cota' if em_pausa else ('falha' if erros else 'concluida'),
                 'pausa_ate': pausa_ate if em_pausa else None,
                 'cursor_consultas': (cursor + executadas) % max(1,len(consultas)), 'consultas_no_catalogo': len(consultas),
                 'consultas_concluidas': executadas - len(erros), 'urls_nesta_execucao': len(encontrados),
                 'erros': erros, 'oportunidades': sorted(itens.values(), key=lambda e: e['url'])}
    destino.parent.mkdir(parents=True, exist_ok=True)
    salvar_json(destino, relatorio)
    resumo = (f'## Descoberta de oportunidades\n\n'
              f'{executadas-len(erros)}/{len(lote)} pesquisas concluídas nesta rodada. '
              f'{len(encontrados)} URLs distintas nesta execução; {len(itens)} no histórico.\n\n'
              'São candidatos: inscrições e elegibilidade ainda precisam de confirmação.\n')
    if em_pausa:
        resumo += f'Busca pausada pelo limite do serviço até {pausa_ate}. Histórico preservado.\n'
    linhas = [resumo, '\n## Candidatos (vigência não verificada)\n']
    for e in relatorio['oportunidades']:
        titulo = str(e.get('titulo') or 'Página sem título').replace('\n', ' ')
        linhas.append(f"- {titulo}: {e['url']}\n")
    Path('data/descobertas.md').write_text(''.join(linhas), encoding='utf-8')
    print(resumo)
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write(resumo)
    if not encontrados and erros and not em_pausa:
        raise SystemExit('Nenhum candidato encontrado: confira o relatório de falhas.')


if __name__ == '__main__':
    descobrir()
