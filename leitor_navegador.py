"""Leitura alternativa de HTML dinâmico, com orçamento e sem sessão autenticada."""
import re
import threading

def precisa_navegador(ctype, bruto):
    if not bruto or 'html' not in (ctype or ''):return False
    html=bruto.decode('utf-8',errors='replace')
    texto=re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>',' ',html,flags=re.I|re.S)
    texto=re.sub(r'<[^>]+>',' ',texto)
    texto=re.sub(r'\s+',' ',texto).strip()
    return len(texto)<180 or bool(re.search(r'Site Unavailable|enable javascript|habilite o javascript',texto,re.I))

def renderizar_html(url, permitido):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        navegador=p.chromium.launch(headless=True)
        try:
            pagina=navegador.new_page()
            def filtrar(rota):
                requisicao=rota.request
                if requisicao.resource_type in ('image','font','media'):
                    return rota.abort()
                if requisicao.is_navigation_request() and not permitido(requisicao.url):
                    return rota.abort()
                return rota.continue_()
            pagina.route('**/*',filtrar)
            resposta=pagina.goto(url,wait_until='domcontentloaded',timeout=25000)
            if resposta and resposta.status>=400:return None,None
            try:pagina.wait_for_load_state('networkidle',timeout=5000)
            except Exception:pass
            html=pagina.content().encode('utf-8')
            return ('text/html',html) if len(html)<=20*1024*1024 else (None,None)
        finally:navegador.close()

def leitor_com_navegador(baixar, permitido, renderizar=None, limite=12):
    renderizar=renderizar or renderizar_html
    trava=threading.Lock()
    estado={'tentativas':0,'sucessos':0,'falhas':0}
    memoria={}
    def ler(url):
        if url in memoria:return memoria[url]
        erro=None
        try:original=baixar(url)
        except Exception as e:
            erro=e
            original=(None,None)
        if not erro and not precisa_navegador(*original):return original
        if not permitido(url):return None,None
        with trava:
            if estado['tentativas']>=limite:
                if erro:raise erro
                return original
            estado['tentativas']+=1
        try:
            resultado=renderizar(url,permitido)
            if resultado[1] and not precisa_navegador(*resultado):
                with trava:
                    estado['sucessos']+=1
                    memoria[url]=resultado
                print('Leitura por navegador concluída: '+url,flush=True)
                return resultado
        except Exception as e:
            print('Leitura por navegador falhou: '+type(e).__name__,flush=True)
        with trava:estado['falhas']+=1
        if erro:raise erro
        return original
    ler.estatisticas=estado
    return ler
