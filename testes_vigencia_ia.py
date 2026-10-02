import unittest
import tempfile
from pathlib import Path
from datetime import datetime
from urllib.error import HTTPError
from vigencia_ia import conferir, Verificador
from validar_vigencia import FUSO

AGORA=datetime(2026,10,2,15,tzinfo=FUSO)
class VigenciaIA(unittest.TestCase):
    def caso(self,titulo,ev,fim,ano=None,situacao='prazo'):
        registro={'url':'https://fonte.gov.br/programa','titulo':titulo,'dados':{'trecho_publico':'Programa para startups','tipo':'Benefícios'}}
        docs={registro['url']:titulo+'\n'+ev}
        d={'situacao':situacao,'fonte':registro['url'],'evidencia_identidade':titulo,'evidencia':ev,'fim':fim,'inicio':None,'evidencia_ano':ano}
        return registro,docs,d
    def test_cinco_revisoes_encerradas(self):
        for titulo,ev,fim,ano in [
            ('Granioter Acelera 2026','Encerramento das inscrições\n30/08/2026','2026-08-30',None),
            ('Acelera Startup SC 2026','Prazo para submissão: 20/05/2026 a 22/06/2026','2026-06-22',None),
            ('Desafio Pantanal Tech 2026','Inscrições abertas até o dia 17 de junho','2026-06-17','Desafio Pantanal Tech 2026'),
            ('Programa Acelera Formiga 2026','Inscrições até o dia 17 de julho','2026-07-17','Programa Acelera Formiga 2026'),
            ('Missão Web Summit Lisboa 2026','Inscrição online até 27/09/2026','2026-09-27',None)]:
            with self.subTest(titulo=titulo):
                r,docs,d=self.caso(titulo,ev,fim,ano)
                docs[r['url']]+='\nDivulgação do resultado: 02/10/2026'
                resultado=conferir(d,docs,r,AGORA)
                self.assertEqual(resultado['status'],'encerrada');self.assertTrue(resultado['prazo_iso'].startswith(fim))
    def test_cronograma_em_blocos_sem_ia(self):
        from validar_vigencia import validar_oficial
        r={'url':'https://fapesc.sc.gov.br/chamada','titulo':'Programa Acelera Startup SC 2026',
           'dados':{'trecho_publico':'Participação para startups'}}
        texto='Programa Acelera Startup SC 2026\nPrazo para submissão:\n20/05/2026 a 22/06/2026\nResultado: 02/10/2026'
        resultado=validar_oficial(r,AGORA,ler=lambda u:texto)
        self.assertEqual(resultado['status'],'encerrada')
        self.assertTrue(resultado['prazo_iso'].startswith('2026-06-22'))
    def test_google_sem_prazo_nao_permanente(self):
        r,docs,d=self.caso('Google Cloud Startup Program','Inscreva-se agora no programa para startups',None,situacao='sem_prazo')
        resultado=conferir(d,docs,r,AGORA)
        self.assertEqual(resultado['modalidade_inscricao'],'candidatura_sem_prazo');self.assertTrue(resultado['sem_data_final'])
    def test_resultado_nao_e_inscricao(self):
        r,docs,d=self.caso('Web Summit Lisboa 2026','Divulgação do resultado final 02/10/2026','2026-10-02')
        with self.assertRaises(ValueError):conferir(d,docs,r,AGORA)
    def test_citacao_inventada(self):
        r,docs,d=self.caso('Pantanal Tech 2026','Inscrições até 17/06/2026','2026-06-17')
        d['evidencia']='Inscrições até 17/12/2026'
        with self.assertRaises(ValueError):conferir(d,docs,r,AGORA)
    def test_ano_nao_assumido(self):
        r,docs,d=self.caso('Pantanal Tech','Inscrições até 17 de junho','2026-06-17')
        with self.assertRaises(ValueError):conferir(d,docs,r,AGORA)
    def test_sem_prazo_com_cronograma_rejeitado(self):
        r,docs,d=self.caso('Google Cloud Startup Program','Inscreva-se agora',None,situacao='sem_prazo');docs[r['url']]+=' Inscrições até 20/12/2026'
        with self.assertRaises(ValueError):conferir(d,docs,r,AGORA)
    def test_fonte_nao_lida_rejeitada(self):
        r,docs,d=self.caso('Programa Alfa 2026','Inscrições até 20/12/2026','2026-12-20');d['fonte']='https://outra.gov.br'
        with self.assertRaises(ValueError):conferir(d,docs,r,AGORA)
    def test_cota_para_e_preserva_pendente(self):
        r,docs,d=self.caso('Programa Alfa 2026','Inscrições até 20/12/2026','2026-12-20')
        chamadas=[]
        def api(c):
            chamadas.append(c);raise HTTPError('https://google.com',429,'quota',{},None)
        with tempfile.TemporaryDirectory() as tmp:
            v=Verificador(chamar=api,cache=str(Path(tmp)/'cache.json'))
            self.assertIsNone(v.verificar(r,docs,AGORA));self.assertIsNone(v.verificar(r,docs,AGORA))
            self.assertEqual(len(chamadas),1);self.assertEqual(v.parada,'gemini_http_429')
    def test_cache_e_limite(self):
        r,docs,d=self.caso('Programa Alfa 2026','Inscrições até 20/12/2026','2026-12-20')
        chamadas=[]
        def api(c):chamadas.append(c);return d
        with tempfile.TemporaryDirectory() as tmp:
            v=Verificador(limite=1,chamar=api,cache=str(Path(tmp)/'cache.json'))
            self.assertEqual(v.verificar(r,docs,AGORA)['status'],'aberta_confirmada')
            self.assertEqual(v.verificar(r,docs,AGORA)['status'],'aberta_confirmada')
            self.assertEqual(len(chamadas),1)
            self.assertIsNone(v.verificar(r,{r['url']:docs[r['url']]+' novo'},AGORA))
if __name__=='__main__':unittest.main()
