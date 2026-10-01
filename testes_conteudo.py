import unittest
from confirmar_oportunidades import conferir, fila

class Conteudo(unittest.TestCase):
    def dados(self):
        return {'oportunidade_concreta':True,'publico_startup':True,'titulo':'Programa 2018',
                'instituicao':'Instituição','tipo':'Missão','resumo':'Programa de participação',
                'trecho_oportunidade':'Programa oferece participação em feira internacional.',
                'trecho_publico':'Podem participar startups de todos os estados.'}
    def test_antiga_aceita_sem_vigencia(self):
        d=self.dados();self.assertTrue(conferir(d,d['trecho_oportunidade']+' '+d['trecho_publico']))
    def test_citacao_inventada_rejeitada(self):
        with self.assertRaises(ValueError): conferir(self.dados(),'Texto diferente e sem a regra apresentada')
    def test_booleano_string_rejeitado(self):
        d=self.dados();d['publico_startup']='true'
        with self.assertRaises(ValueError): conferir(d,'qualquer texto')
    def test_diversifica_dominios(self):
        itens=[{'url':u,'categoria':'prioridade_verificacao'} for u in ['https://a.br/1','https://a.br/2','https://b.br/1']]
        self.assertEqual([e['url'] for e in fila(itens,{},2)],['https://a.br/1','https://b.br/1'])
    def test_nao_reprocessa_confirmado(self):
        e={'url':'https://a.br/1','categoria':'prioridade_verificacao'}
        from confirmar_oportunidades import VERSAO
        self.assertEqual(fila([e],{e['url']:{'versao':VERSAO,'status':'confirmada_no_conteudo'}},60),[])

if __name__=='__main__':unittest.main()
