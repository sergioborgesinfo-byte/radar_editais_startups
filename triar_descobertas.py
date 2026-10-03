"""Triagem conservadora por título e URL, sem avaliar datas ou afirmar vigência."""
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))


def canon(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        return None
    host = p.hostname.lower().removeprefix('www.')
    params = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True)
              if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]
    # Agrupa versões HTTP/HTTPS da mesma página, preservando edição no caminho e parâmetros.
    return urlunsplit(('https', host, p.path.rstrip('/') or '/', urlencode(sorted(params)), ''))


def classificar(e):
    t = norm(str(e.get('titulo', '')))
    p = urlsplit(e['url'])
    if re.search(r'(?:disable|desativar|startup programs?).*windows|windows.*startup|high schools?|selecao (?:de |para )?bolsista|selecao de bolsa', t):
        return 'fora_escopo', 'Inicialização de computador, competição escolar ou seleção de pessoa bolsista; não é candidatura de startup'
    if p.hostname in ('darwinstartups.com', 'www.darwinstartups.com') and p.path.rstrip('/') == '/icmlab':
        return 'prioridade_verificacao', 'Página oficial indicada de programa com inscrições; conteúdo e vigência ainda serão verificados'
    if re.search(r'monografia|dissertacao|tese de |analise critica da metodologia|metodologia lean startup', t):
        return 'fora_escopo', 'Conteúdo acadêmico sobre startups, não anúncio de participação'
    if re.search(r'selecao de fundo|selecao de gestor|fip conexoes', t):
        return 'fora_escopo', 'Seleção de fundo ou gestor; participação direta de startups não demonstrada'
    if re.search(r'capta |captou |levanta |levantou |compra |adquire |aquisicao|country manager|vagas de emprego', t):
        return 'fora_escopo', 'Notícia de mercado, contratação ou transação, sem chamada identificada no título'
    if p.path.rstrip('/') in ('', '/index/programas', '/pt') or re.search(r'\b(company|in)/[^/]+$', p.path) and 'linkedin.com' in p.netloc:
        return 'fonte_catalogo', 'Página institucional ou catálogo: serve para descobrir chamadas individuais'
    if 'programas.sebraestartups.com.br' in p.netloc and p.path.startswith('/in/'):
        return 'prioridade_verificacao', 'Página individual de programa Sebrae; regras ainda não verificadas'
    if re.search(r'edital|chamada|inscri|selecao|desafio|challenge|aceleracao|aceleradora|incubacao|incubadora|missao|rodada.*negocio|exposicao.*startup|manifestacao de interesse|programa.*startup|startup.*program|premio|fomento|subvencao|bolsa', t):
        return 'prioridade_verificacao', 'Título indica possível programa ou oportunidade; pode ser notícia ou chamada antiga'
    return 'revisar_contexto', 'Título insuficiente; precisa ler o conteúdo antes de decidir'


def triar(dados):
    grupos = {}
    for e in dados['oportunidades']:
        chave = canon(e['url'])
        if not chave:
            continue
        if chave in grupos:
            grupos[chave]['links_equivalentes'].append(e['url'])
            continue
        categoria, motivo = classificar(e)
        grupos[chave] = {'titulo': e.get('titulo',''), 'url': e['url'], 'categoria': categoria,
                         'motivo': motivo, 'links_equivalentes': [e['url']],
                         'vigencia': 'nao_avaliada'}
    itens = list(grupos.values())
    contagem = dict(Counter(e['categoria'] for e in itens))
    sebrae = [e for e in itens if 'programas.sebraestartups.com.br/in/' in e['url']]
    return {'executado_em': datetime.now(timezone.utc).isoformat(), 'metodo': 'Triagem preliminar por título e URL; sem leitura integral ou filtro de prazo',
            'links_recebidos': len(dados['oportunidades']), 'paginas_agrupadas': len(itens),
            'duplicacoes_de_url': len(dados['oportunidades'])-len(itens), 'contagem': contagem,
            'programas_sebrae': len(sebrae), 'itens': itens}


def main():
    origem = Path('data/oportunidades-descobertas.json')
    r = triar(json.loads(origem.read_text(encoding='utf-8')))
    Path('data/triagem-descobertas.json').write_text(json.dumps(r, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    linhas = ['# Triagem da descoberta — vigência não avaliada\n\n',
              'Classificação preliminar por título e URL. Não comprova elegibilidade ou inscrições abertas. Nenhum candidato foi apagado.\n\n',
              f"{r['links_recebidos']} links recebidos; {r['paginas_agrupadas']} páginas após agrupar {r['duplicacoes_de_url']} duplicações de URL.\n\n",
              f"{r['programas_sebrae']} páginas individuais do catálogo Sebrae encontradas.\n\n"]
    for categoria in ('prioridade_verificacao','fonte_catalogo','revisar_contexto','fora_escopo'):
        linhas.append(f"## {categoria}: {r['contagem'].get(categoria,0)}\n\n")
        for e in r['itens']:
            if e['categoria']==categoria:
                titulo=str(e['titulo']).replace('\n',' ').replace('[','').replace(']','')
                linhas.append(f"- [{titulo or 'Sem título'}]({e['url']}) — {e['motivo']}.\n")
        linhas.append('\n')
    Path('data/triagem-descobertas.md').write_text(''.join(linhas), encoding='utf-8')
    print(json.dumps({k:v for k,v in r.items() if k!='itens'},ensure_ascii=False))
    if 'GITHUB_STEP_SUMMARY' in __import__('os').environ:
        with open(__import__('os').environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:
            f.write(''.join(linhas[:4])+str(r['contagem'])+'\n')


if __name__=='__main__':
    main()
