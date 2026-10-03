import json
import os
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from estado_pipeline import Orcamento, salvar_json
from executar_pipeline import progresso
from pesquisar_fontes import candidatos_compativeis


class Pipeline(unittest.TestCase):
    def test_orcamento_compartilhado_nao_multiplica_por_etapa(self):
        with tempfile.TemporaryDirectory() as tmp:
            orcamento = Orcamento(8, Path(tmp)/'estado.json')
            orcamento.limites_etapa['conteudo'] = 3
            for _ in range(3): self.assertIsNone(orcamento.reservar('conteudo'))
            self.assertEqual(orcamento.reservar('conteudo'), 'orcamento_etapa_esgotado')
            for _ in range(5): self.assertIsNone(orcamento.reservar('vigencia'))
            self.assertEqual(orcamento.reservar('vigencia'), 'orcamento_execucao_esgotado')
            self.assertEqual(orcamento.usadas, 8)

    def test_cota_pausa_as_demais_etapas_e_proxima_execucao(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'estado.json'
            orcamento = Orcamento(8, path)
            orcamento.pausar()
            self.assertEqual(orcamento.reservar('vigencia'), 'gemini_cota_em_pausa')
            outro = Orcamento(8, path)
            self.assertEqual(outro.reservar('conteudo'), 'gemini_cota_em_pausa')
            self.assertEqual(outro.usadas, 0)

    def test_falha_de_gravacao_preserva_arquivo_anterior(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'dados.json'; salvar_json(p, {'itens':[1,2]})
            with patch('estado_pipeline.os.replace', side_effect=OSError):
                with self.assertRaises(OSError): salvar_json(p, {'itens':[3]})
            self.assertEqual(json.loads(p.read_text()), {'itens':[1,2]})
            self.assertEqual(list(Path(tmp).glob('*.tmp')), [])

    def test_rodada_sem_mudanca_nao_e_avanco(self):
        foto={'situacoes':{'a':'pendente_evidencia','b':'aberta_confirmada'}, 'abertas_publicadas':1}
        self.assertEqual(progresso(foto,foto)['casos_concluidos_nesta_rodada'],0)

    def test_discrimina_encerrada_excluida_e_nova_aberta(self):
        antes={'situacoes':{'a':'pendente_evidencia','b':'pendente_evidencia'}, 'abertas_publicadas':0}
        depois={'situacoes':{'a':'encerrada','b':'fora_escopo','c':'aberta_confirmada'}, 'abertas_publicadas':1}
        d=progresso(antes,depois)
        self.assertEqual(d['casos_concluidos_nesta_rodada'],3)
        self.assertEqual(d['concluidos_por_resultado'],{'encerrada':1,'fora_escopo':1,'aberta_confirmada':1})
        self.assertEqual(d['saldo_abertas'],1)

    def test_pesquisa_rejeita_edicao_estado_e_blog_incompativeis(self):
        r={'titulo':'Centelha Paraná 2026'}
        hits=[{'url':'https://fonte.gov.br/1','title':'Centelha Paraná 2024','content':'Inscrições'},
              {'url':'https://fonte.gov.br/2','title':'Centelha Santa Catarina 2026','content':'Inscrições'},
              {'url':'https://blog.com/3','title':'Centelha Paraná 2026','content':'Inscrições'},
              {'url':'https://fonte.gov.br/4','title':'Centelha Paraná 2026','content':'Inscrições abertas'}]
        self.assertEqual(candidatos_compativeis(r,hits,lambda url:'.gov.br' in url),['https://fonte.gov.br/4'])

    def test_pesquisa_sai_na_primeira_cota_e_preserva_fila(self):
        from pesquisar_fontes import executar
        from requests import HTTPError, Response
        with tempfile.TemporaryDirectory() as tmp:
            antigo=os.getcwd(); os.chdir(tmp)
            try:
                salvar_json('data/oportunidades-vigencia.json',{'itens':[{'url':'https://noticia.com/'+str(i),'titulo':'Programa Alfa 2026','status':'pendente_fonte_oficial'} for i in range(3)]})
                resposta=Response(); resposta.status_code=432
                pesquisar=unittest.mock.Mock(side_effect=HTTPError(response=resposta))
                d=executar(pesquisar=pesquisar)
                self.assertEqual(d['consultas'],1)
                self.assertEqual(d['motivo'],'busca_cota_em_pausa')
                self.assertEqual(executar(pesquisar=pesquisar)['consultas'],0)
                self.assertEqual(pesquisar.call_count,1)
            finally: os.chdir(antigo)

    def test_cache_ia_nao_muda_por_metadado_do_registro(self):
        from vigencia_ia import Verificador
        from validar_vigencia import FUSO
        r={'url':'https://fonte.gov.br/a','titulo':'Programa Alfa 2026'}
        docs={r['url']:'Programa Alfa 2026. Inscrições até 20/12/2026'}
        resposta={'situacao':'prazo','fonte':r['url'],'evidencia_identidade':r['titulo'],
                  'evidencia':'Inscrições até 20/12/2026','fim':'2026-12-20','inicio':None}
        with tempfile.TemporaryDirectory() as tmp:
            api=unittest.mock.Mock(return_value=resposta)
            v=Verificador(chamar=api,cache=str(Path(tmp)/'cache.json'))
            agora=datetime(2026,10,3,tzinfo=FUSO)
            self.assertEqual(v.verificar(r,docs,agora)['status'],'aberta_confirmada')
            r['conferido_em']='outro horário';r['tentativas']=4
            self.assertEqual(v.verificar(r,docs,agora)['status'],'aberta_confirmada')
            self.assertEqual(api.call_count,1)

    def test_fora_escopo_nao_confunde_concurso_escolar_com_startup(self):
        from triar_descobertas import classificar
        for titulo in ['How to Disable Startup Programs in Windows','Startup Venture Challenge for High Schools','Programa Startup Lab – Seleção de Bolsista']:
            self.assertEqual(classificar({'url':'https://fonte.gov.br/a','titulo':titulo})[0],'fora_escopo')

    def test_falha_de_uma_etapa_nao_esconde_resultado_nem_afirma_sucesso(self):
        from executar_pipeline import main
        with tempfile.TemporaryDirectory() as tmp:
            antigo=os.getcwd(); os.chdir(tmp)
            try:
                salvar_json('docs/busca.json', {'itens':[], 'confirmacoes':[]})
                def validar():
                    salvar_json('data/oportunidades-vigencia.json',{'itens':[{'url':'https://fonte.gov.br/a','status':'encerrada'}]})
                with patch('estado_pipeline.orcamento', None), patch('triar_descobertas.main', return_value=None), \
                     patch('confirmar_oportunidades.main', side_effect=ValueError('falha')), \
                     patch('pesquisar_fontes.executar', return_value={'consultas':0}), \
                     patch('validar_vigencia.main', side_effect=validar):
                    with self.assertRaises(SystemExit): main()
                r=json.loads(Path('data/execucao-pipeline.json').read_text())
                self.assertEqual(r['status'],'falha_parcial')
                self.assertEqual(r['casos_concluidos_nesta_rodada'],1)
                self.assertEqual(r['etapas'][-1]['status'],'concluida')
                self.assertEqual(json.loads(Path('docs/busca.json').read_text())['pipeline']['status'],'falha_parcial')
            finally: os.chdir(antigo)
