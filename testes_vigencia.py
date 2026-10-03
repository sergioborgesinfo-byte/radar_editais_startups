import io
import json
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from validar_vigencia import validar_sebrae, validar_oficial, exportar_abertas, deduplicar, data_literal, texto_relevante, atualizar_acompanhamento, oficial

FUSO=ZoneInfo('America/Sao_Paulo')

class Vigencia(unittest.TestCase):
    def test_fluxo_continuo_vinculado_ao_nome_nos_paragrafos_anteriores(self):
        r={'url':'https://cbamazonia.org/edital','titulo':'Edital de Fluxo Contínuo CBA Open nº 01/2026',
           'dados':{'trecho_publico':'Startups e empresas de base tecnológica'}}
        t='O CBA lançou o Edital CBA Open nº 01/2026. O chamamento seleciona empresas. O edital contempla empresas com CNPJ. As inscrições permanecerão abertas em fluxo contínuo.'
        v=validar_oficial(r,datetime(2026,10,2,tzinfo=FUSO),lambda _:t)
        self.assertEqual(v['status'],'aberta_confirmada')
        self.assertTrue(v['sem_data_final'])
        errado=validar_oficial(r,datetime(2026,10,2,tzinfo=FUSO),lambda _:'Programa XYZ: inscrições abertas em fluxo contínuo.')
        self.assertEqual(errado['status'],'pendente_evidencia')
    def test_fluxo_continuo_em_blocos_separados_com_ano_no_cabecalho(self):
        casos = [
            ({'url':'https://inatel.br/startups/edital.pdf',
              'titulo':'Edital Inatel Startups - Seleção de Novos Projetos / Empresas',
              'dados':{'trecho_publico':'inscrições para projetos e startups inovadoras'}},
             'EDITAL INATEL STARTUPS\nPERÍODO DE VIGÊNCIA: FLUXO CONTÍNUO\nABERTURA: 10/05/2024\nENCERRAMENTO: NÃO SE APLICA\nEstão abertas as inscrições para o processo seletivo de projetos e startups inovadoras.'),
            ({'url':'https://mamiraua.org.br/nits',
              'titulo':'Processo de Seleção de Propostas para Incubação e Aceleração – Fluxo Contínuo',
              'dados':{'trecho_publico':'empresas, associações, pessoas físicas, startups'}},
             'Incubadora Mamirauá\nO EDITAL Nº 01/2024 seleciona interessados.\nDe fluxo contínuo.\nA inscrição será feita por formulário eletrônico. Startups podem participar.')
        ]
        for registro, texto in casos:
            with self.subTest(registro=registro['url']):
                resultado=validar_oficial(registro,datetime(2026,10,3,tzinfo=FUSO),lambda _:texto)
                self.assertEqual(resultado['status'],'aberta_confirmada')
                self.assertTrue(resultado['sem_data_final'])
                self.assertEqual(resultado['evidencia_edicao'],'2024')

    def test_icm_lab_oficial_com_publico_e_prazo_literal(self):
        from validar_vigencia import validar_oficial
        r={'url':'https://www.darwinstartups.com/icmlab',
           'titulo':'ICM Lab Solana — Darwin Startups',
           'dados':{'titulo':'ICM Lab Solana — Darwin Startups',
                    'tipo':'Aceleração',
                    'resumo':'Programa de aceleração focado em infraestrutura.',
                    'trecho_oportunidade':'ICM Lab Solana é um programa de aceleração.',
                    'trecho_publico':'Nosso objetivo é selecionar até 10 startups.'}}
        texto=('ICM Lab Solana powered by Darwin Startups.\n'
               'Nosso objetivo é selecionar e impulsionar de perto até 10 startups.\n'
               'Cadastros abertos de 14 de setembro de 2026 até 11 de outubro de 2026.')
        d=validar_oficial(r,datetime(2026,10,2,tzinfo=FUSO),lambda _:texto)
        self.assertEqual(d['status'],'aberta_confirmada')
        self.assertEqual(d['tipo'],'Aceleração')
        self.assertEqual(d['prazo'],'2026-10-11')
        self.assertIn('Cadastros abertos',d['evidencia_prazo'])

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
    def test_intervalo_usa_data_final_literal(self):
        self.assertEqual(data_literal('Prazo para submissão: 05/05/2026 a 15/06/2026').date().isoformat(),'2026-06-15')
    def test_texto_longo_preserva_prazo_no_final(self):
        texto='A'*31000+'\nPrazo para submissão: 05/05/2026 a 15/06/2026'
        self.assertIn('15/06/2026',texto_relevante(texto,30000))
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

    def test_ano_historico_no_texto_nao_comprova_edicao_atual(self):
        r={'url':'https://cob.org.br/desafio','titulo':'Desafio COB de Startups',
           'dados':{'trecho_publico':'Startups podem participar'}}
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:'Depois de reunir startups em 2025, recebe inscrições até 10 de janeiro de 2027.')
        self.assertEqual(v['status'],'pendente_evidencia')
        self.assertEqual(v['motivo'],'edicao_ou_publico_nao_comprovado')

    def test_data_mais_recente_de_outra_chamada_nao_substitui_prazo(self):
        r={'url':'https://fapemig.br/centelha','titulo':'Programa Centelha 2026',
           'dados':{'trecho_publico':'Podem participar startups brasileiras'}}
        v=validar_oficial(r,datetime(2026,10,1,12,tzinfo=FUSO),
            lambda u:'Centelha recebe inscrições até 31/08/2026. British Council recebe inscrições até 15/10/2026.')
        self.assertEqual(v['status'],'encerrada')
        self.assertIn('31/08/2026',v['evidencia_prazo'])

    def test_fonte_oficial_mapeada_usa_cronograma_da_pagina_dedicada(self):
        r={'url':'https://rtm.net.br/darwin-startups-abre-inscricoes-para-15a-turma-de-aceleracao',
           'titulo':'Darwin Startups abre inscrições para 15ª turma de aceleração',
           'dados':{'trecho_publico':'Programa de aceleração para startups'}}
        acessada=[]
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:(acessada.append(u) or 'Batch #15 Darwin Startups 2026. Inscrições: de 26 de agosto a 25 de setembro de 2026.'))
        self.assertIn('darwinstartups.com/batch15',acessada[0])
        self.assertEqual(v['status'],'encerrada')

    def test_catalogo_estruturado_fapemig_usa_cronograma_da_chamada(self):
        r={'url':'https://fapemig.br/oportunidades/chamadas-e-editais/chamada-fapemig-sede-013-2026-pesquisador-na-empresa',
           'titulo':'CHAMADA FAPEMIG-SEDE 013/2026 - PESQUISADOR NA EMPRESA',
           'dados':{'trecho_publico':'Empresas, startups e cooperativas de Minas Gerais'}}
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:'Data Início de Submissão de Propostas: 13/07/2026\nData Final de Submissão de Propostas: 31/08/2026')
        self.assertEqual(v['status'],'encerrada')
        self.assertIn('31/08/2026',v['evidencia_prazo'])

    def test_cba_e_fonte_oficial_e_fluxo_continuo(self):
        url='https://cbamazonia.org/cba-lanca-edital-de-fluxo-continuo-para-atrair-startups-e-empresas-inovadoras-voltadas-a-bioeconomia-amazonica'
        self.assertTrue(oficial(url))
        r={'url':url,'titulo':'CBA Open 2026',
           'dados':{'titulo':'Edital de Fluxo Contínuo CBA Open nº 01/2026',
                    'trecho_publico':'O edital contempla empresas com até 10 anos de CNPJ',
                    'trecho_oportunidade':'O CBA lançou edital para startups e empresas de base tecnológica',
                    'resumo':'Residência no Hub de Bionegócios'}}
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:'CBA Open 2026 para startups. As inscrições permanecerão abertas em fluxo contínuo.')
        self.assertEqual(v['status'],'aberta_confirmada')
        self.assertTrue(v['sem_data_final'])

    def test_rio_ia_usa_fonte_publica_e_prazo_prorrogado(self):
        r={'url':'https://convergenciadigital.com.br/mercado/programa-rio-ia-2026-vai-investir-r-640-mil-em-startups',
           'titulo':'Programa Rio.IA 2026 vai investir em startups',
           'dados':{'titulo':'1º Edital do Programa de Inovação Aberta do Hub Rio.IA – 2026',
                    'trecho_publico':'O edital selecionará até oito startups'}}
        acessada=[]
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:(acessada.append(u) or 'Startups podem participar. Inscrições prorrogadas até 06/02/2026.'))
        self.assertIn('prosas.com.br/editais/16756',acessada[0])
        self.assertEqual(v['status'],'encerrada')

    def test_randon_2024_usa_fonte_corporativa_e_nao_reaparece(self):
        r={'url':'https://dana.com.br/canaldana/2024/07/25/randoncorp-abre-inscricoes-para-segunda-turma-do-programa-de-aceleracao-de-startups',
           'titulo':'Randoncorp abre inscrições para segunda turma',
           'dados':{'trecho_publico':'Programa de aceleração para startups'}}
        acessada=[]
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:(acessada.append(u) or 'Segunda turma da Randon Ventures. Startups podem se inscrever até 9 de agosto de 2024.'))
        self.assertIn('randoncorp.com',acessada[0])
        self.assertEqual(v['status'],'encerrada')

    def test_portal_governamental_portugues_e_fonte_oficial(self):
        url='https://portugal.gov.pt/gc25/comunicacao/comunicados/programa-para-startups'
        self.assertTrue(oficial(url))
        r={'url':url,'titulo':'Abertas candidaturas ao programa de aceleração',
           'dados':{'trecho_publico':'Programa dirigido a startups de base científica'}}
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:'Candidaturas abertas entre 16 de junho e 3 de julho. Programa decorre até dezembro de 2026.')
        self.assertEqual(v['status'],'pendente_evidencia')
        self.assertEqual(v['motivo'],'edicao_ou_publico_nao_comprovado')

    def test_startup_sc_usa_pagina_oficial_da_turma_2026(self):
        r={'url':'https://www.startupsc.com.br/programa-de-capacitacao-startup-sc',
           'titulo':'Programa Startup SC – Sebrae Startups',
           'dados':{'trecho_publico':'Programa gratuito para startups incubadas na Rede MIDIHUB'}}
        acessada=[]
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:(acessada.append(u) or '16ª Turma do Programa Startup SC. Inscrições para startups de 02 de fevereiro a 08 de março de 2026.'))
        self.assertIn('startupsc.com.br/inscreva-se',acessada[0])
        self.assertEqual(v['status'],'encerrada')
        self.assertIn('08 de março de 2026',v['evidencia_prazo'])

    def test_data_de_abertura_nao_e_tratada_como_prazo_final(self):
        r={'url':'https://www.startupsc.com.br/programa-de-capacitacao-startup-sc',
           'titulo':'Programa Startup SC – Sebrae Startups',
           'dados':{'trecho_publico':'Programa gratuito para startups incubadas'}}
        v=validar_oficial(r,datetime(2026,10,2,12,tzinfo=FUSO),
            lambda u:'16ª Turma do Programa Startup SC 2026. Inscrições abertas a partir de 02/02/2026.')
        self.assertEqual(v['status'],'pendente_evidencia')
        self.assertEqual(v['motivo'],'prazo_literal_com_ano_nao_encontrado')

class Atualizacao(unittest.TestCase):
    def item(self):
        return {'status':'aberta_confirmada','titulo':'Programa X','instituicao':'X',
                'tipo':'Seleção','estagio':'Qualquer','descricao':'Apoio','url':'https://x.org.br',
                'prazo':'2026-10-02','prazo_iso':'2026-10-02T23:59:59-03:00',
                'inicio_iso':None,'requisitos':'Startups','modalidade_inscricao':'selecao',
                'evidencia_edicao':'2026','evidencia_publico':'Startups',
                'evidencia_prazo':'Até 02/10/2026',
                'verificado_em':'2026-10-01T12:00:00-03:00'}

    def test_expirada_nao_republica_mesmo_status_aberto(self):
        self.assertEqual(exportar_abertas([self.item()], datetime(2026,10,3,0,tzinfo=FUSO)), [])

    def test_preserva_hora_real_e_limita_validade_ao_prazo(self):
        e=self.item()
        saida=exportar_abertas([e], datetime(2026,10,2,12,tzinfo=FUSO))[0]
        self.assertEqual(saida['verificado_em'],e['verificado_em'])
        self.assertEqual(saida['verificacao_valida_ate'],e['prazo_iso'])

    def test_sem_hora_de_verificacao_exige_releitura(self):
        e=self.item(); del e['verificado_em']
        self.assertEqual(exportar_abertas([e],datetime(2026,10,2,12,tzinfo=FUSO)),[])

    def test_fluxo_continuo_expira_em_24_horas(self):
        e=self.item(); e.update(sem_data_final=True,prazo=None,prazo_iso=None)
        self.assertEqual(exportar_abertas([e],datetime(2026,10,2,12,tzinfo=FUSO)),[])

    def test_inscricao_futura_nao_publica(self):
        e=self.item(); e['inicio_iso']='2026-10-02T18:00:00-03:00'
        self.assertEqual(exportar_abertas([e],datetime(2026,10,2,12,tzinfo=FUSO)),[])


if __name__=='__main__': unittest.main()
