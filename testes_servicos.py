"""Testes sem rede para credenciais e recuperação de falhas."""
import importlib.util
import io
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
spec = importlib.util.spec_from_file_location('conferir_servicos', Path(__file__).with_name('conferir_servicos.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)

class Servicos(unittest.TestCase):
    def test_chave_pura(self):
        self.assertEqual(s.limpar_chave(' tvly-exemplo '),'tvly-exemplo')
    def test_env_aspas(self):
        self.assertEqual(s.limpar_chave('TAVILY_API_KEY="tvly-exemplo"'),'tvly-exemplo')
        self.assertEqual(s.limpar_chave("export GEMINI_API_KEY='exemplo'"),'exemplo')
    def test_multiplas_chaves(self):
        with self.assertRaises(ValueError):s.limpar_chave('TAVILY_API_KEY=a\nGEMINI_API_KEY=b')
    def test_vazio(self):
        with self.assertRaises(ValueError):s.limpar_chave('GEMINI_API_KEY=""')
    def test_401_sem_expor_chave(self):
        with patch.object(s,'urlopen',side_effect=HTTPError('https://exemplo',401,'',{},None)) as abrir, patch.object(s.time,'sleep') as dormir:
            with self.assertRaises(RuntimeError) as erro:s.consultar('Tavily','https://exemplo',{'Authorization':'Bearer segredo'},{})
            self.assertNotIn('segredo',str(erro.exception));self.assertEqual(abrir.call_count,1);dormir.assert_not_called()
    def test_500_recupera(self):
        with patch.object(s,'urlopen',side_effect=[HTTPError('https://exemplo',500,'',{},None),io.BytesIO(b'{"ok":true}')]) as abrir, patch.object(s.time,'sleep'):
            self.assertTrue(s.consultar('Gemini','https://exemplo',{}, {})['ok']);self.assertEqual(abrir.call_count,2)
    def test_503_limite_tentativas(self):
        with patch.object(s,'urlopen',side_effect=[HTTPError('https://exemplo',503,'',{},None) for _ in range(3)]) as abrir, patch.object(s.time,'sleep'):
            with self.assertRaises(RuntimeError):s.consultar('Gemini','https://exemplo',{}, {})
            self.assertEqual(abrir.call_count,3)
if __name__=='__main__':unittest.main()
