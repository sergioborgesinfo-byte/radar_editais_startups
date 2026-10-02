import unittest
from unittest.mock import patch
from fontes_primarias import selecionar_links
from validar_vigencia import oficial, validar_oficial, FUSO
from datetime import datetime

class FontesPrimarias(unittest.TestCase):
    def test_segue_edital_identificado_e_ignora_rodape(self):
        html='<a href="https://fapesc.sc.gov.br/edital-nascer-2026">Regulamento Programa Nascer</a><a href="https://www.gov.br/privacidade">Privacidade</a>'
        urls=selecionar_links(html,'https://noticias.com/nascer','Programa Nascer 2026',oficial)
        self.assertEqual(urls,['https://fapesc.sc.gov.br/edital-nascer-2026'])

    def test_nao_segue_prazo_de_outro_programa(self):
        html='<a href="https://www.gov.br/edital-british-council">Inscrições British Council</a>'
        self.assertEqual(selecionar_links(html,'https://noticia.com/centelha','Centelha Paraíba 2026',oficial),[])

    def test_mirror_e_link_nao_oficial_nao_servem_como_fonte(self):
        html='<a href="https://blog.com/edital-centelha">Inscrições Centelha</a>'
        self.assertEqual(selecionar_links(html,'https://noticia.com/centelha','Centelha 2026',oficial),[])

    def test_link_relativo_resolvido_sem_duplicacao(self):
        html='<a href="/edital-centelha#regras">Inscrições Centelha</a><a href="/edital-centelha">Regulamento Centelha</a>'
        self.assertEqual(selecionar_links(html,'https://fapesc.sc.gov.br/noticia','Centelha 2026',oficial),['https://fapesc.sc.gov.br/edital-centelha'])

    def test_fonte_descoberta_nao_permite_data_de_outra_chamada(self):
        r={'url':'https://noticias.com/centelha','titulo':'Centelha 2026',
           'fonte_primaria_descoberta':'https://fapesc.sc.gov.br/centelha',
           'dados':{'trecho_publico':'Podem participar startups brasileiras'}}
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
                         lambda url:'Centelha 2026 apoia startups. British Council recebe inscrições até 15/10/2026.')
        self.assertEqual(v['status'],'pendente_evidencia')

    def test_valida_regra_na_fonte_primaria_automaticamente(self):
        import sys,types
        r={'url':'https://noticias.com/centelha','titulo':'Centelha 2026',
           'dados':{'trecho_publico':'Podem participar startups brasileiras'}}
        fake=types.SimpleNamespace(baixar=lambda url:('text/html',b'pagina'),
                                   para_texto=lambda c,b:'Centelha recebe inscrições até 15/10/2026.',MAX_CHARS=30000)
        with patch('fontes_primarias.localizar',return_value=['https://fapesc.sc.gov.br/centelha']),patch.dict(sys.modules,radar=fake):
            v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO))
        self.assertEqual(v['status'],'aberta_confirmada')
        self.assertEqual(v['fonte_oficial'],'https://fapesc.sc.gov.br/centelha')

    def test_pdf_oficial_rotulado_aqui(self):
        html='<a href="https://www.gov.br/documentos/arquivo-2026.pdf">Clique aqui</a>'
        self.assertEqual(selecionar_links(html,'https://noticia.com/centelha','Centelha Paraná 2026',oficial),
                         ['https://www.gov.br/documentos/arquivo-2026.pdf'])

    def test_indice_exige_identidade_e_mesma_edicao(self):
        import tempfile,json
        from pathlib import Path
        from fontes_primarias import fontes_do_indice
        registro={'url':'https://noticia.com/centelha','titulo':'Centelha Paraná 2026'}
        itens=[{'url':'https://www.gov.br/centelha-pr','titulo':'Centelha Paraná 2026'},
               {'url':'https://www.gov.br/centelha-sc','titulo':'Centelha Santa Catarina 2026'},
               {'url':'https://www.gov.br/centelha-antigo','titulo':'Centelha Paraná 2024'},
               {'url':'https://blog.com/centelha','titulo':'Centelha Paraná 2026'}]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'indice.json';p.write_text(json.dumps({'itens':itens}))
            self.assertEqual(fontes_do_indice(registro,oficial,p),['https://www.gov.br/centelha-pr'])
