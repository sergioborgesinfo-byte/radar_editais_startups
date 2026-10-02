import unittest
import io
import json
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


class Recuperacao(unittest.TestCase):
    def test_servico_falha_preserva_fila_e_confirmacoes(self):
        from confirmar_oportunidades import executar, ServicoIndisponivel
        lote=[{'url':f'https://a.br/{i}'} for i in range(3)]
        feitos={'https://anterior.br':{'status':'confirmada_no_conteudo'}}
        chamadas=[]
        def classificar(texto,url):
            chamadas.append(url)
            raise ServicoIndisponivel('gemini_http_429')
        n,parada=executar(lote,feitos,lambda u:('Texto suficiente',None),classificar,lambda d:None)
        self.assertEqual((n,parada),(3,'gemini_http_429'))
        self.assertEqual(len(chamadas),1)
        self.assertEqual(feitos[lote[1]['url']]['status'],'pendente_ia')
        self.assertEqual(feitos[lote[0]['url']]['status'],'pendente_ia')
        self.assertEqual(feitos['https://anterior.br']['status'],'confirmada_no_conteudo')

    def test_falha_pagina_nao_consume_ia(self):
        from confirmar_oportunidades import executar
        feitos={}
        n,parada=executar([{'url':'https://a.br'}],feitos,
            lambda u:(None,'robots_bloqueou_leitura'),
            lambda t,u:self.fail('Não deve chamar IA'),lambda d:None)
        self.assertEqual(feitos['https://a.br']['motivo'],'robots_bloqueou_leitura')
        self.assertIsNone(parada)

    def test_prioriza_fontes_sem_excluir_outros_sites(self):
        from confirmar_oportunidades import fila
        itens=[{'url':u,'categoria':'prioridade_verificacao'} for u in
            ['https://blog.br/1','https://programas.sebraestartups.com.br/in/1','https://fapesc.sc.gov.br/1']]
        self.assertEqual(fila(itens,{},3)[0]['url'],itens[1]['url'])
        self.assertEqual(len(fila(itens,{},3)),3)

    def test_http_429_interrompe_sem_repeticao(self):
        from unittest.mock import patch
        from urllib.error import HTTPError
        from confirmar_oportunidades import classificar_texto, ServicoIndisponivel
        with patch.dict('os.environ',{'GEMINI_API_KEY':'test'}), patch('confirmar_oportunidades.time.sleep'), patch('confirmar_oportunidades.urlopen',side_effect=HTTPError('https://service',429,'quota',{},None)) as req:
            with self.assertRaises(ServicoIndisponivel) as erro:
                classificar_texto('texto','https://a.br')
        self.assertEqual(erro.exception.codigo,'gemini_http_429')
        self.assertEqual(req.call_count,1)

class Evidencias(unittest.TestCase):
    def test_convite_literal_sem_ia(self):
        from confirmar_oportunidades import evidencias_textuais
        texto='Podem participar do programa de aceleração startups de todo o Brasil.'
        d=evidencias_textuais(texto,{'titulo':'Programa de aceleração','url':'https://fonte.br/1'})
        self.assertTrue(conferir(d,texto))

    def test_mencao_generica_nao_confirma(self):
        from confirmar_oportunidades import evidencias_textuais
        d=evidencias_textuais('O programa publicou os resultados. Startups fazem parte do ecossistema.',
                             {'titulo':'Programa','url':'https://fonte.br/1'})
        self.assertIsNone(d)

    def test_continua_evidencias_apos_quota(self):
        from confirmar_oportunidades import executar, ServicoIndisponivel
        itens=[{'url':'https://a.br/1'}, {'url':'https://b.br/1','titulo':'Programa de aceleração'}]
        feitos={}
        def ler(url):
            return ('Texto sem prova' if 'a.br' in url else 'Podem participar do programa de aceleração startups de todo o Brasil.', None)
        def ia(t,u):
            raise ServicoIndisponivel('gemini_http_429')
        executar(itens,feitos,ler,ia,lambda d:None)
        self.assertEqual(feitos['https://b.br/1']['status'],'confirmada_no_conteudo')

    def test_glossario_nao_comprova_programa(self):
        from confirmar_oportunidades import evidencias_textuais
        self.assertIsNone(evidencias_textuais('A aceleradora oferece mentorias para startups em um programa completo.',
            {'titulo':'Programa ACE Startups','url':'https://fonte.br/glossario/ace'}))
    def test_beneficiario_indireto_nao_comprova_candidatura(self):
        from confirmar_oportunidades import evidencias_textuais
        self.assertIsNone(evidencias_textuais('Programas de aceleração para startups oferecem mentoria e fomento por meio de ambientes de inovação.',
            {'titulo':'Chamada de aceleração','url':'https://fonte.br/1'}))

    def test_icm_lab_confirma_sem_ia_com_citacoes_literais_separadas(self):
        from confirmar_oportunidades import auditar_confirmacoes, evidencias_textuais
        texto=('ICM Lab Solana powered by Darwin Startups, um programa de aceleração focado em infraestrutura.\n'
               'Nosso objetivo é selecionar e impulsionar de perto até 10 startups na aceleração.\n'
               'Cadastros abertos de 14 de setembro de 2026 até 11 de outubro de 2026.')
        e={'titulo':'ICM Lab Solana — Darwin Startups',
           'url':'https://www.darwinstartups.com/icmlab'}
        d=evidencias_textuais(texto,e)
        self.assertEqual(d['metodo'],'regra_oficial_icm_lab')
        self.assertNotEqual(d['trecho_oportunidade'], d['trecho_publico'])
        self.assertTrue(conferir(d,texto))
        feitos={e['url']:{'url':e['url'],'status':'confirmada_no_conteudo','dados':d}}
        self.assertEqual(auditar_confirmacoes(feitos),0)
        self.assertEqual(feitos[e['url']]['status'],'confirmada_no_conteudo')

    def test_icm_lab_auditado_volta_a_fila_sem_repetir_ia(self):
        from confirmar_oportunidades import fila
        e={'titulo':'ICM Lab Solana — Darwin Startups',
           'url':'https://www.darwinstartups.com/icmlab',
           'categoria':'prioridade_verificacao'}
        feitos={e['url']:{'status':'pendente_evidencia',
                          'auditoria_relevancia':'requer_revisao'}}
        self.assertEqual(fila([e],feitos,1),[e])


class ProgressoFila(unittest.TestCase):
    def test_pendente_nao_bloqueia_pagina_nova(self):
        from confirmar_oportunidades import fila
        itens=[{'url':url,'categoria':'prioridade_verificacao'} for url in ['https://fonte.gov.br/antiga','https://fonte.gov.br/nova','https://outra.br/nova']]
        feitos={itens[0]['url']:{'status':'pendente_ia','tentativas':2}}
        escolhidas=fila(itens,feitos,2)
        self.assertEqual([x['url'] for x in escolhidas],[itens[1]['url'],itens[2]['url']])


class CoberturaGlobal(unittest.TestCase):
    def test_inedito_outro_dominio_antes_de_repeticao(self):
        itens = [{'url': u, 'categoria': 'prioridade_verificacao'} for u in
                 ['https://a.gov.br/antiga', 'https://b.br/nova']]
        feitos = {itens[0]['url']: {'status': 'pendente_ia', 'tentativas': 1}}
        self.assertEqual(fila(itens, feitos, 1), [itens[1]])

    def test_repeticoes_ainda_entram_quando_sobram_vagas(self):
        itens = [{'url': u, 'categoria': 'prioridade_verificacao'} for u in
                 ['https://a.gov.br/antiga', 'https://b.br/nova']]
        feitos = {itens[0]['url']: {'status': 'pendente_ia', 'tentativas': 1}}
        self.assertEqual(fila(itens, feitos, 2), [itens[1], itens[0]])

    def test_prioritarios_precedem_contexto_mesmo_em_outro_dominio(self):
        contexto={'url':'https://a.br/noticia','categoria':'revisar_contexto'}
        prioritario={'url':'https://z.gov.br/edital','categoria':'prioridade_verificacao'}
        self.assertEqual(fila([contexto, prioritario], {}, 1), [prioritario])

    def test_auditoria_nao_e_reprocessada_com_ia(self):
        e={'url':'https://a.br/case','categoria':'prioridade_verificacao'}
        feitos={e['url']:{'status':'pendente_evidencia','auditoria_relevancia':'requer_revisao'}}
        self.assertEqual(fila([e], feitos, 1), [])


class PaginaDinamica(unittest.TestCase):
    def test_caso_mercopar_vem_primeiro(self):
        mercopar = {'url':'https://programas.sebraestartups.com.br/in/1783963246760x826977266273542100','categoria':'prioridade_verificacao'}
        outro = {'url':'https://sebrae.com.br/programa','categoria':'prioridade_verificacao'}
        self.assertEqual(fila([outro, mercopar], {}, 1), [mercopar])

    def test_recupera_dados_oficiais_do_sebrae(self):
        from confirmar_oportunidades import recuperar_sebrae_dinamico
        corpo = json.dumps([{'id':'1783963246760x826977266273542100','data': {'titulo_text':'Startups na Mercopar 2026 (Manifestação de interesse)',
                    'descricao_text':'Podem participar startups do Brasil interessadas na feira.'}}]).encode()
        class Resposta(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): pass
        texto = recuperar_sebrae_dinamico(
            'https://programas.sebraestartups.com.br/in/1783963246760x826977266273542100',
            lambda req, timeout: Resposta(corpo))
        self.assertIn('Manifestação de interesse', texto)
        self.assertIn('Podem participar startups', texto)

    def test_429_preservado_nao_marca_workflow_como_quebrado(self):
        from confirmar_oportunidades import falha_execucao
        self.assertFalse(falha_execucao('gemini_http_429'))
        self.assertTrue(falha_execucao('limite_tempo; candidatos restantes preservados'))


class AuditoriaRelevancia(unittest.TestCase):
    def registro(self, url, titulo, evidencia):
        return {'url':url, 'status':'confirmada_no_conteudo', 'dados':{
            'titulo':titulo, 'trecho_oportunidade':evidencia, 'trecho_publico':evidencia}}

    def test_rejeita_case_comercial(self):
        from confirmar_oportunidades import auditar_confirmacoes
        r=self.registro('https://empresa.br/cases/programa', 'Case do programa',
                        'Apoiamos a curadoria de startups e a divulgação para atrair inscrições.')
        auditar_confirmacoes({'x':r})
        self.assertEqual(r['status'], 'pendente_evidencia')


class GateQualidade(unittest.TestCase):
    def registro(self, url, titulo, evidencia):
        return {'url':url, 'status':'confirmada_no_conteudo', 'dados':{
            'titulo':titulo, 'trecho_oportunidade':evidencia, 'trecho_publico':evidencia}}

    def test_nao_avanca_com_cobertura_incompleta(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from confirmar_oportunidades import salvar_qualidade
        mercopar='https://programas.sebraestartups.com.br/in/1783963246760x826977266273542100'
        origem={'itens':[{'url':mercopar,'categoria':'prioridade_verificacao'},
                         {'url':'https://outra.br/chamada','categoria':'prioridade_verificacao'}]}
        feitos={mercopar:{'url':mercopar,'status':'confirmada_no_conteudo'}}
        with tempfile.TemporaryDirectory() as pasta, patch('confirmar_oportunidades.Path',
                side_effect=lambda nome: Path(pasta) / Path(nome).name):
            r=salvar_qualidade(origem,feitos,{'confirmada_no_conteudo':1})
        self.assertFalse(r['avancar_vigencia'])
        self.assertEqual(r['cobertura_prioritaria'],.5)

    def test_rejeita_registro_historico_sem_chamada_atual(self):
        from confirmar_oportunidades import auditar_confirmacoes
        r=self.registro('https://fonte.br/programa', 'Programa para startups',
                        'Em 2018 o programa recebeu inscrições e selecionou 74 startups.')
        auditar_confirmacoes({'x':r})
        self.assertEqual(r['status'], 'pendente_evidencia')

    def test_mantem_convite_direto(self):
        from confirmar_oportunidades import auditar_confirmacoes
        r=self.registro('https://fonte.gov.br/edital', 'Edital 2026 para startups',
                        'Estão abertas as inscrições do edital 2026 para startups brasileiras.')
        self.assertEqual(auditar_confirmacoes({'x':r}), 0)
        self.assertEqual(r['status'], 'confirmada_no_conteudo')

    def test_nao_confunde_proibicao_com_convite(self):
        from confirmar_oportunidades import auditar_confirmacoes
        r=self.registro('https://fonte.br/programa', 'Aceleração de startups',
                        'Durante o programa as startups não podem participar de concorrentes.')
        auditar_confirmacoes({'x':r})
        self.assertEqual(r['status'], 'pendente_evidencia')

    def test_chamada_para_ambientes_nao_e_para_startups(self):
        from confirmar_oportunidades import auditar_confirmacoes
        r=self.registro('https://fonte.gov.br/chamada', 'Chamada de aceleração de startups',
                        'Fomento a programas de aceleração promovidos por ambientes de inovação.')
        auditar_confirmacoes({'x':r})
        self.assertEqual(r['status'], 'pendente_evidencia')
