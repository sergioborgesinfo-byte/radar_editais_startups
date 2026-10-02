import unittest
from leitor_navegador import leitor_com_navegador, precisa_navegador

class LeitorNavegador(unittest.TestCase):
    def test_html_dinamico_recebe_conteudo_renderizado(self):
        completo=('text/html',('<article>Programa para startups: inscrições até 20/12/2026. '+('Conteúdo público. '*30)+'</article>').encode())
        l=leitor_com_navegador(lambda u:('text/html',b'<main id="app"></main>'),lambda u:True,lambda u,p:completo)
        self.assertEqual(l('https://fonte.gov.br'),completo)
        self.assertEqual(l.estatisticas['sucessos'],1)
    def test_robots_nao_recebe_tentativa_alternativa(self):
        chamadas=[]
        l=leitor_com_navegador(lambda u:(None,None),lambda u:False,lambda u,p:chamadas.append(u))
        self.assertEqual(l('https://fonte.gov.br'),(None,None));self.assertEqual(chamadas,[])
    def test_pdf_nao_vai_ao_navegador(self):
        self.assertFalse(precisa_navegador('application/pdf',b'%PDF-fonte'))
    def test_orcamento_limita_fontes_indisponiveis(self):
        chamadas=[]
        def render(u,p):chamadas.append(u);return None,None
        l=leitor_com_navegador(lambda u:('text/html',b'Site Unavailable'),lambda u:True,render,limite=1)
        l('https://fonte.gov.br/1');l('https://fonte.gov.br/2')
        self.assertEqual(len(chamadas),1)
