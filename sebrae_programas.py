"""Leitura de uma oportunidade do Sebrae pelo endpoint usado pela própria página."""
import json
import re
from urllib.parse import quote, unquote, urlsplit
from urllib.request import Request, urlopen

def ler_programa(url, abrir=urlopen):
    p = urlsplit(url)
    if p.hostname != 'programas.sebraestartups.com.br' or not p.path.startswith('/in/'):
        return None
    slug = unquote(p.path.rstrip('/').rsplit('/', 1)[-1])
    req = Request(f'https://{p.netloc}/api/1.1/init/data?location={quote(url, safe="")}',
                  headers={'User-Agent':'RadarStartups/1.0'})
    with abrir(req, timeout=20) as resposta:
        registros = json.load(resposta)
    registros = [r for r in registros if isinstance(r, dict) and isinstance(r.get('data'), dict)] if isinstance(registros, list) else []
    ids = re.findall(r'\d{13}x\d+', slug)
    correspondentes = [r for r in registros if r.get('id') == slug or r.get('id') in ids
                       or r['data'].get('Slug') == slug]
    if len(correspondentes) == 1:
        return correspondentes[0]['data']
    # O endpoint location retorna o registro daquela página, mesmo sem campo Slug.
    # Nunca escolhe o primeiro registro de uma resposta com vários programas.
    if not ids and len(registros) == 1 and registros[0]['data'].get('titulo_text'):
        return registros[0]['data']
    return None

def texto_programa(dados):
    return '\n'.join(str(dados.get(c, '')) for c in
                     ('titulo_text', 'descricao_breve_text', 'descricao_text', 'instrucao_requerente_text'))
