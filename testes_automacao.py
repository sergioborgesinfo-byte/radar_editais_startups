"""Testes sem rede, sem APIs e sem importar bibliotecas externas."""
from pathlib import Path
from datetime import timedelta
from types import SimpleNamespace
import ast
import importlib.util
import os
import re
import sqlite3
import unittest
from contextlib import redirect_stdout
from io import StringIO

raiz = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("radar_automacao", raiz / "radar_automacao.py")
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class Automacao(unittest.TestCase):
    def setUp(self):
        saida = redirect_stdout(StringIO())
        saida.__enter__()
        self.addCleanup(saida.__exit__, None, None, None)
        self.con = sqlite3.connect(":memory:")
        self.con.row_factory = sqlite3.Row
        self.con.executescript('''
        CREATE TABLE editais(id TEXT PRIMARY KEY, url TEXT, fonte TEXT, titulo TEXT,
          orgao TEXT, tipo TEXT, estagio TEXT, descricao TEXT, valor REAL, prazo TEXT,
          requisitos TEXT, trecho_prazo TEXT, revisar INTEGER, criado_em TEXT,
          atualizado_em TEXT);
        CREATE TABLE paginas(url TEXT PRIMARY KEY, hash TEXT, visto_em TEXT);
        ''')
        a.preparar(self.con, {"fontes": [], "programas": []})
        self.prazo = (a.agora().date() + timedelta(days=2)).isoformat()
        self.texto = "Instituto oficial. Startups podem participar. Inscrições até " + self.prazo + ". Edital 01/2026."
        self.d = dict(e_edital=True, publico_startup=True, titulo="Edital 01/2026",
                      orgao="IFRN", tipo="Incubação", estagio="Qualquer",
                      trecho_publico="Startups podem participar.",
                      fonte_responsavel=True, trecho_responsavel="Instituto oficial.",
                      prazo_inscricao=self.prazo, trecho_prazo="Inscrições até " + self.prazo,
                      prazo_e_inscricao=True, prazo_hora=None,
                      identificador_edital="01/2026")
        self.total = dict(novo=0, atualizado=0, ignorado=0, erro=0)
        def gravar(con, nome, url, d, revisar):
            con.execute("INSERT OR REPLACE INTO editais VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        ("edital", url, nome, d["titulo"], d["orgao"], d["tipo"],
                         d["estagio"], "Descrição", None, d["prazo_inscricao"],
                         "Startups", d["trecho_prazo"], int(revisar),
                         a.agora().isoformat(), a.agora().isoformat()))
            return "novo"
        self.r = SimpleNamespace(
            baixar=lambda url: ("text/html", self.texto.encode()),
            para_texto=lambda c, b: b.decode(), extrair=lambda t, u: self.d.copy(),
            conferir_resposta=lambda d: d, norm=lambda t: re.sub(r"\s+", " ", (t or "").lower()).strip(),
            validar=lambda d, t: (d, False), gravar=gravar,
            chave=lambda o, t: "edital", _agora=a.agora, os=SimpleNamespace(getenv=lambda k: None),
            buscar_aberta=lambda *args: [],
        )

    def tearDown(self):
        self.con.close()

    def coletar(self, url="https://portal.ifrn.edu.br/edital"):
        return a.processar(self.r, self.con, "Teste", url, self.total)

    def test_fonte_e_evidencias_publicam(self):
        self.assertTrue(self.coletar())
        self.assertEqual(len(a.selecionados(self.con)), 1)

    def test_registro_antigo_sem_evidencias_nao_publica(self):
        self.r.gravar(self.con, "Antigo", "https://portal.ifrn.edu.br/edital", self.d, False)
        self.assertEqual(a.selecionados(self.con), [])

    def test_fonte_secundaria_nao_publica(self):
        self.assertFalse(self.coletar("https://pt.scribd.com/document/123"))
        self.assertEqual(a.selecionados(self.con), [])

    def test_gov_br_de_outro_responsavel_nao_publica(self):
        self.assertFalse(self.coletar("https://www.mpc.pr.gov.br/apresentacao.pdf"))

    def test_publico_nao_literal_nao_publica(self):
        self.d["trecho_publico"] = "Texto inventado"
        self.assertFalse(self.coletar())

    def test_data_de_resultado_nao_publica(self):
        self.d["prazo_e_inscricao"] = False
        self.assertFalse(self.coletar())
        self.assertEqual(a.selecionados(self.con), [])

    def test_evidencia_expirada_nao_publica(self):
        self.coletar()
        self.con.execute("UPDATE verificacoes_automaticas SET conferido_em=?",
                         ((a.agora() - timedelta(hours=49)).isoformat(),))
        self.assertEqual(a.selecionados(self.con), [])

    def test_data_vencida_nao_publica(self):
        self.d["prazo_inscricao"] = (a.agora().date() - timedelta(days=1)).isoformat()
        self.coletar()
        self.assertEqual(a.selecionados(self.con), [])

    def test_horario_vencido_nao_publica(self):
        self.coletar()
        self.con.execute("UPDATE verificacoes_automaticas SET limite_iso=?",
                         ((a.agora() - timedelta(minutes=1)).isoformat(),))
        self.assertEqual(a.selecionados(self.con), [])

    def test_horario_inventado_nao_publica(self):
        self.d["prazo_hora"] = "17:00"
        self.assertFalse(self.coletar())

    def test_mesma_pagina_nao_chama_ia_duas_vezes(self):
        self.coletar()
        self.r.extrair = lambda *args: self.fail("IA chamada duas vezes")
        a._visitadas.clear()
        self.assertTrue(self.coletar())

    def test_reconfere_mesmo_hash_apos_22_horas(self):
        self.coletar()
        self.con.execute("UPDATE verificacoes_automaticas SET conferido_em=?",
                         ((a.agora() - timedelta(hours=23)).isoformat(),))
        self.con.commit()
        chamadas = []
        self.r.extrair = lambda *args: chamadas.append(1) or self.d.copy()
        a._visitadas.clear()
        self.coletar()
        self.assertEqual(len(chamadas), 1)

    def test_erro_na_gravacao_desfaz_hash(self):
        def falhar(con, *args):
            con.execute("INSERT INTO paginas VALUES('alteracao','hash','data')")
            raise ValueError("Falha simulada")
        self.r.gravar = falhar
        self.assertFalse(self.coletar())
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM paginas").fetchone()[0], 0)

    def test_mesma_edicao_duplicada(self):
        self.assertTrue(a._duplicado(
            dict(url="https://a", chave_edicao="org|01 2026", orgao="Órgão", titulo="Edital 01/2026"),
            dict(url="https://b", chave_edicao="org|01 2026", orgao="Órgão", titulo="Chamada 01/2026")))

    def test_edicoes_distintas_preservadas(self):
        self.assertFalse(a._duplicado(
            dict(url="https://a", chave_edicao="org|01 2026", orgao="Órgão", titulo="Edital 01/2026"),
            dict(url="https://b", chave_edicao="org|02 2026", orgao="Órgão", titulo="Edital 02/2026")))

    def test_resolve_fonte_oficial_e_confere_de_novo(self):
        urls_extraidas = []
        def extrair(t, url):
            urls_extraidas.append(url)
            d = self.d.copy()
            d["fonte_responsavel"] = "portal.ifrn.edu.br" in url
            return d
        self.r.extrair = extrair
        self.r.os = SimpleNamespace(getenv=lambda k: "chave-de-teste")
        self.r.buscar_aberta = lambda *args: ["https://portal.ifrn.edu.br/edital"]
        self.assertTrue(self.coletar("https://pt.scribd.com/document/123"))
        publicados = a.selecionados(self.con)
        self.assertEqual(len(publicados), 1)
        self.assertEqual(publicados[0]["url"], "https://portal.ifrn.edu.br/edital")
        self.assertEqual(len(urls_extraidas), 2)

    def test_url_com_credenciais_nao_e_institucional(self):
        self.assertFalse(a.institucional("https://usuario:senha@portal.ifrn.edu.br/"))

    def test_aberta_sem_data_com_evidencia_publica(self):
        self.d.update(prazo_inscricao=None, prazo_e_inscricao=False, sem_data_final=True,
                      inscricoes_abertas=True, trecho_abertura="Inscrições abertas para startups")
        self.texto += " Inscrições abertas para startups"
        self.assertTrue(self.coletar())
        self.assertEqual(len(a.selecionados(self.con)), 1)
        self.assertTrue(a.selecionados(self.con)[0]["sem_data_final"])

    def test_sem_data_sem_abertura_nao_publica(self):
        self.d.update(prazo_inscricao=None, prazo_e_inscricao=False, sem_data_final=True,
                      inscricoes_abertas=True, trecho_abertura="Texto inventado")
        self.assertFalse(self.coletar())
        self.assertEqual(a.selecionados(self.con), [])

    def test_nao_transforma_vencido_em_continuo(self):
        self.d.update(prazo_inscricao=(a.agora().date()-timedelta(days=1)).isoformat(),
                      sem_data_final=True, inscricoes_abertas=True, trecho_abertura="Startups podem participar.")
        self.coletar()
        self.assertEqual(a.selecionados(self.con), [])

    def test_sem_data_expira_evidencia_em_24_horas(self):
        self.d.update(prazo_inscricao=None, prazo_e_inscricao=False, sem_data_final=True,
                      inscricoes_abertas=True, trecho_abertura="Inscrições abertas para startups")
        self.texto += " Inscrições abertas para startups"
        self.coletar()
        self.con.execute("UPDATE verificacoes_automaticas SET conferido_em=?", ((a.agora()-timedelta(hours=25)).isoformat(),))
        self.assertEqual(a.selecionados(self.con), [])


if __name__ == "__main__":
    unittest.main()
