import io
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from validar_vigencia import validar_sebrae, validar_oficial, exportar_abertas, deduplicar, data_literal, atualizar_acompanhamento

FUSO=ZoneInfo('America/Sao_Paulo')

class Vigencia(unittest.TestCase):
    def registro(self):
        return {'url':'https://programas.sebraestartups.com.br/in/1783963246760x826977266273542100',
                'titulo':'Mercopar 2026', 'dados':{'trecho_publico':'Startups do RS e demais estados'}}
    def abrir(self, fim=1790996399000, ativo=True):
        corpo=json.dumps([{'id':'1783963246760x826977266273542100','data':{
            'ativo_boolean':ativo,'data_inicio_date':1784689200000,'data_final_date':fim,
            'titulo_text':'Startups na Mercopar 2026 (Manifestação de interesse)',
            'descricao_breve_text':'Feira de inovação industrial para startups.',
            'descricao_text':'Startups selecionadas terão espaço na feira.'}}]).encode()
        class R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self,*args): pass
        return lambda req,timeout:R(corpo)
    def test_manifestacao_aberta_sem_chamar_de_selecao(self):
        r=validar_sebrae(self.registro(),datetime(2026,10,1,12,tzinfo=FUSO),self.abrir())
        self.assertEqual(r['status'],'aberta_confirmada')
        self.assertEqual(r['tipo'],'Manifestação de interesse')
        self.assertEqual(r['prazo'],'2026-10-02')
    def test_encerrada_nao_publica(self):
        r=validar_sebrae(self.registro(),datetime(2026,10,3,12,tzinfo=FUSO),self.abrir())
        self.assertEqual(r['status'],'encerrada')
        self.assertEqual(exportar_abertas([r],datetime(2026,10,3,12,tzinfo=FUSO)),[])
    def test_inativa_nao_publica(self):
        r=validar_sebrae(self.registro(),datetime(2026,10,1,12,tzinfo=FUSO),self.abrir(ativo=False))
        self.assertEqual(r['status'],'pendente_evidencia')
    def test_deduplica_mesma_oportunidade(self):
        a={'titulo':'Programa X','instituicao':'Órgão','prazo_iso':'2026-10-02T23:59:59-03:00'}
        b=dict(a);b['prazo_iso']='2026-10-03T23:59:59-03:00'
        self.assertEqual(deduplicar([a,b]),[b])
    def test_deduplica_fluxo_continuo_sem_prazo(self):
        a={'titulo':'Programa X','instituicao':'Órgão','prazo_iso':None}
        b=dict(a)
        self.assertEqual(deduplicar([a,b]),[a])
    def test_data_sem_ano_nao_e_inferida(self):
        self.assertIsNone(data_literal('Inscrições até 21 de agosto'))
    def test_oficial_encerrada_nao_publica(self):
        r={'url':'https://agifes.ifes.edu.br/programa','titulo':'Horizontes 2026',
           'dados':{'titulo':'Horizontes 2026 para startups','trecho_publico':'Startups e projetos inovadores'}}
        v=validar_oficial(r,datetime(2026,10,1,12,tzinfo=FUSO),
                         lambda u:'Horizontes: inscrições estão abertas até 27 de fevereiro de 2026.')
        self.assertEqual(v['status'],'encerrada')
    def test_oficial_aberta_exige_prazo_literal(self):
        r={'url':'https://fapemig.br/edital','titulo':'Centelha 2026',
           'dados':{'titulo':'Centelha 2026 para startups','trecho_publico':'Podem participar startups brasileiras','resumo':'Apoio'}}
        v=validar_oficial(r,datetime(2026,10,1,12,tzinfo=FUSO),
                         lambda u:'Centelha: prazo para submissão: 15/10/2026.')
        self.assertEqual(v['status'],'aberta_confirmada')
        self.assertEqual(v['prazo'],'2026-10-15')

    def test_prazo_de_outra_noticia_nao_confirma_centelha(self):
        r={'url':'https://news.confap.org.br/centelha','titulo':'Programa Centelha Paraíba',
           'dados':{'trecho_publico':'Podem participar startups brasileiras'}}
        v=validar_oficial(r,datetime(2026,10,1,12,tzinfo=FUSO),
            lambda u:'Centelha 2026 apoia startups. O British Council recebe, até 15 de outubro de 2026, inscrições para Study UK Alumni Awards 2027.')
        self.assertEqual(v['status'],'pendente_evidencia')

    def test_data_mais_recente_de_outra_chamada_nao_substitui_prazo(self):
        r={'url':'https://fapemig.br/centelha','titulo':'Programa Centelha 2026',
           'dados':{'trecho_publico':'Podem participar startups brasileiras'}}
        v=validar_oficial(r,datetime(2026,10,1,12,tzinfo=FUSO),
            lambda u:'Centelha recebe inscrições até 31/08/2026. British Council recebe inscrições até 15/10/2026.')
        self.assertEqual(v['status'],'encerrada')
        self.assertIn('31/08/2026',v['evidencia_prazo'])

if __name__=='__main__': unittest.main()
