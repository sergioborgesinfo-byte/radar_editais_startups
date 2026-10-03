import unittest
from datetime import datetime
from cronogramas import datas, prazo_documentado, FUSO

class Cronogramas(unittest.TestCase):
    def test_article_so_com_titulo_nao_oculta_corpo_irmao(self):
        from cronogramas import ler_texto
        t=ler_texto('text/html',b'<main><article><h1>Novo SEED 2026</h1></article><div><p>Data Final de Submissao de Propostas: 23/04/2026</p></div></main>')
        self.assertEqual(prazo_documentado(t,'Novo SEED 2026')['fim'].date().isoformat(),'2026-04-23')
    def test_noticia_nao_usa_prazo_de_cartao_de_outra_edicao(self):
        from cronogramas import ler_texto
        html=('<main><article><h1>Desafio COB de Startups ja soma mais de 100 inscricoes</h1><p>Inscricoes encerradas em 08/08/2025.</p><p>'+('Descricao do programa. '*20)+'</p></article><article>Desafio COB de Startups recebe inscricoes ate 10/01/2027.</article></main>').encode()
        t=ler_texto('text/html',html)
        self.assertNotIn('2027',t)
        self.assertEqual(prazo_documentado(t,'Desafio COB de Startups ja soma mais de 100 inscricoes')['fim'].date().isoformat(),'2025-08-08')
    def test_cartao_article_nao_oculta_cronograma_do_main(self):
        from cronogramas import ler_texto
        html=b'<main><h1>Novo SEED 2026</h1><article>Categoria A</article><p>Data Final de Submissao de Propostas: 23/04/2026</p><p>Resultado: 16/07/2026</p></main>'
        t=ler_texto('text/html',html)
        r=prazo_documentado(t,'Novo SEED 2026')
        self.assertEqual(r['fim'].date().isoformat(),'2026-04-23')
    def test_portugues_periodo_ano_no_final(self):
        r=prazo_documentado('IncubaScience CETENE\nInscrições\n05 de maio a 05 de junho de 2026\nHomologação das Inscrições\n10 de junho de 2026','IncubaScience CETENE')
        self.assertEqual(r['fim'].date().isoformat(),'2026-06-05')
        self.assertEqual(r['inicio'].date().isoformat(),'2026-05-05')
    def test_ingles_cronograma_data_antes(self):
        t='Hello Tomorrow Global Challenge\n23 September 2026\nApplications open\n30 November 2026\nApplications close\nJune 2, 2027\nHello Tomorrow Summit'
        r=prazo_documentado(t,'Hello Tomorrow Challenge')
        self.assertEqual(r['fim'].date().isoformat(),'2026-11-30')
        self.assertEqual(r['inicio'].date().isoformat(),'2026-09-23')
    def test_texto_real_linha_do_tempo_ingles(self):
        t='Hello Tomorrow Challenge\nNovember 30th, 2026 - Applications Close\nFebruary 2027 - Deep Tech Pioneers Selected\nJune 2nd-3rd, 2027 - Hello Tomorrow Summit'
        r=prazo_documentado(t,'Hello Tomorrow Challenge')
        self.assertEqual(r['fim'].date().isoformat(),'2026-11-30')
        self.assertNotIn('Selected',r['evidencia'])
    def test_ingles_data_com_ordinal(self):
        for s in ['Applications deadline November 30th, 2026','Applications close 30th November 2026']:
            self.assertEqual(prazo_documentado('Hello Tomorrow\n'+s,'Hello Tomorrow')['fim'].month,11)
    def test_ano_ausente_vinculado_edicao(self):
        r=prazo_documentado('Desafio Pantanal Tech 2026\nInscrições abertas até 17 de junho','Desafio Pantanal Tech 2026')
        self.assertEqual(r['fim'].date().isoformat(),'2026-06-17')
    def test_ano_nao_presumido(self):
        self.assertIsNone(prazo_documentado('Desafio Pantanal Tech\nInscrições até 17 de junho','Desafio Pantanal Tech'))
    def test_resultado_nao_e_prazo(self):
        self.assertIsNone(prazo_documentado('IncubaScience CETENE\nHomologação das inscrições\n10 de junho de 2026','IncubaScience CETENE'))
    def test_abertura_nao_e_encerramento(self):
        self.assertIsNone(prazo_documentado('Hello Tomorrow\n23 September 2026 Applications open','Hello Tomorrow'))
    def test_programa_diferente(self):
        self.assertIsNone(prazo_documentado('British Council\nInscrições até 30/11/2026','Centelha Paraná'))
    def test_datas_iso(self):
        self.assertEqual(datas('2026-11-30')[0].date().isoformat(),'2026-11-30')
    def test_data_invalida(self):
        self.assertEqual(datas('31 de fevereiro de 2026'),[])
    def test_etapa_seguinte_nao_conectada(self):
        self.assertIsNone(prazo_documentado('IncubaScience CETENE\nInscrições\nHomologação das Inscrições\n10 de junho de 2026','IncubaScience CETENE'))
class CacheLeitura(unittest.TestCase):
    def test_reutiliza_entre_execucoes(self):
        import tempfile
        from leitura_cache import leitor_cache
        chamadas=[]
        def baixar(url):chamadas.append(url);return 'text/html',b'<p>Fonte publica</p>'
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(leitor_cache(baixar,tmp)('https://fonte.gov.br')[1],b'<p>Fonte publica</p>')
            self.assertEqual(leitor_cache(baixar,tmp)('https://fonte.gov.br')[1],b'<p>Fonte publica</p>')
            self.assertEqual(len(chamadas),1)
    def test_falha_nao_e_cacheada_entre_execucoes(self):
        import tempfile
        from leitura_cache import leitor_cache
        chamadas=[]
        def baixar(url):chamadas.append(url);return None,None
        with tempfile.TemporaryDirectory() as tmp:
            leitor_cache(baixar,tmp)('https://fonte.gov.br')
            leitor_cache(baixar,tmp)('https://fonte.gov.br')
            self.assertEqual(len(chamadas),2)
if __name__=='__main__':unittest.main()
