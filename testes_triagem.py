import unittest
from triar_descobertas import classificar, canon, triar

class Triagem(unittest.TestCase):
    def test_nao_filtra_ano(self):
        for ano in ('2018','2026'):
            self.assertEqual(classificar({'titulo':'Edital incubação '+ano,'url':'https://instituicao.br/edital/'+ano})[0], 'prioridade_verificacao')
    def test_catalogo_nao_e_chamada(self):
        self.assertEqual(classificar({'titulo':'Programas startups','url':'https://programas.sebraestartups.com.br/index/programas'})[0],'fonte_catalogo')
    def test_programa_individual_sebrae(self):
        self.assertEqual(classificar({'titulo':'Mercopar','url':'https://programas.sebraestartups.com.br/in/123'})[0],'prioridade_verificacao')
    def test_programa_oficial_darwin_indicado(self):
        self.assertEqual(classificar({'titulo':'ICM Lab Solana — Darwin Startups','url':'https://www.darwinstartups.com/icmlab'})[0],'prioridade_verificacao')
    def test_gestor_nao_e_startup(self):
        self.assertEqual(classificar({'titulo':'Chamada seleção de fundo FIP Conexões','url':'https://bndes.gov.br/chamada'})[0],'fora_escopo')
    def test_preserva_edicoes(self):
        self.assertNotEqual(canon('https://site.br/edital?edicao=1'),canon('https://site.br/edital?edicao=2'))
    def test_agrupa_tracking(self):
        r=triar({'oportunidades':[{'titulo':'Edital','url':'https://site.br/edital?utm_source=a'},{'titulo':'Edital','url':'https://site.br/edital'}]})
        self.assertEqual(r['duplicacoes_de_url'],1)
        self.assertEqual(r['itens'][0]['vigencia'],'nao_avaliada')

if __name__=='__main__': unittest.main()
