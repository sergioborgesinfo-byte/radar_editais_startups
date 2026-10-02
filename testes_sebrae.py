import io
import json
import unittest
from datetime import datetime
from sebrae_programas import ler_programa
from validar_vigencia import validar_sebrae, FUSO

class SebraeEstruturado(unittest.TestCase):
    def abrir(self, registros):
        return lambda req, timeout: io.BytesIO(json.dumps(registros).encode())

    def registro(self, identificador='1766082380128x779845055372993000'):
        return {'id': identificador, 'data': {'titulo_text': 'Feiras e Eventos 2026',
                'descricao_breve_text': 'Manifestação de interesse para startups exporem em feiras.',
                'ativo_boolean': True, 'data_final_date': 1798772399000,
                'data_inicio_date': 1767236400000}}

    def test_slug_sem_campo_slug_resolve_registro_unico(self):
        d=ler_programa('https://programas.sebraestartups.com.br/in/feiras2026',self.abrir([self.registro()]))
        self.assertEqual(d['titulo_text'],'Feiras e Eventos 2026')

    def test_resposta_ambigua_nao_escolhe_primeiro_programa(self):
        self.assertIsNone(ler_programa('https://programas.sebraestartups.com.br/in/feiras2026',
                          self.abrir([self.registro(),self.registro('outro')])) )

    def test_id_incorreto_nao_usa_programa_de_outra_pagina(self):
        self.assertIsNone(ler_programa('https://programas.sebraestartups.com.br/in/1773155744320x304125193997948540',
                          self.abrir([self.registro()])))

    def test_slug_com_identificador_embutido(self):
        d=ler_programa('https://programas.sebraestartups.com.br/in/feiras-1766082380128x779845055372993000',
                      self.abrir([self.registro(),self.registro('outro')]))
        self.assertEqual(d['titulo_text'],'Feiras e Eventos 2026')

    def test_futuro_nao_e_aberto(self):
        r=self.registro();r['data']['data_inicio_date']=1798772398000
        v=validar_sebrae({'url':'https://programas.sebraestartups.com.br/in/feiras2026'},
                        datetime(2026,10,2,12,tzinfo=FUSO),self.abrir([r]))
        self.assertEqual(v['status'],'ainda_nao_aberta')

    def test_publico_nao_startup_nao_publica(self):
        r=self.registro();r['data']['descricao_breve_text']='Inscrições de docentes para vagas de emprego.'
        v=validar_sebrae({'url':'https://programas.sebraestartups.com.br/in/feiras2026'},
                        datetime(2026,10,2,12,tzinfo=FUSO),self.abrir([r]))
        self.assertEqual(v['status'],'pendente_evidencia')

    def test_encerrado_inativo_e_identificado(self):
        r=self.registro();r['data'].update(ativo_boolean=False,data_final_date=1692845994000)
        v=validar_sebrae({'url':'https://programas.sebraestartups.com.br/in/feiras2026'},
                        datetime(2026,10,2,12,tzinfo=FUSO),self.abrir([r]))
        self.assertEqual(v['status'],'encerrada')
