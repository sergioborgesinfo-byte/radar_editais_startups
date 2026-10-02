import io
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from validar_vigencia import validar_sebrae, exportar_abertas, deduplicar

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

if __name__=='__main__': unittest.main()
