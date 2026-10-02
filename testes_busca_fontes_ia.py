import unittest
import tempfile
from datetime import datetime,timezone
from busca_fontes_ia import BuscaFontes,links_citados

class Busca(unittest.TestCase):
    def test_usa_apenas_citacoes_e_fontes_oficiais(self):
        r={'candidates':[{'content':{'parts':[{'text':'https://inventado.gov.br'}]},
           'groundingMetadata':{'groundingChunks':[{'web':{'uri':'https://blog.com'}},
           {'web':{'uri':'https://vertexaisearch.cloud.google.com/redirect'}},
           {'web':{'uri':'https://senha@www.gov.br'}}]}}]}
        self.assertEqual(links_citados(r,lambda _: 'https://www.gov.br/edital',lambda u:'.gov.br' in u),['https://www.gov.br/edital'])
    def test_cache_e_limite_impedem_repeticao(self):
        with tempfile.TemporaryDirectory() as t:
            b=BuscaFontes(1,lambda _: {'candidates':[]},caminho=t+'/cache.json')
            agora=datetime.now(timezone.utc)
            b.buscar({'url':'https://a'},lambda _:True,agora)
            b.buscar({'url':'https://a'},lambda _:True,agora)
            b.buscar({'url':'https://b'},lambda _:True,agora)
            self.assertEqual(b.chamadas,1)
    def test_falha_nao_interrompe_verificacao(self):
        def falhar(_):raise TimeoutError()
        with tempfile.TemporaryDirectory() as t:
            b=BuscaFontes(chamar=falhar,caminho=t+'/cache.json')
            self.assertEqual(b.buscar({'url':'https://a'},lambda _:True,datetime.now(timezone.utc)),[])
            self.assertEqual(b.erros[0]['tipo'],'TimeoutError')
