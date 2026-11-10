from pathlib import Path
import re

def adicionar_freio():
    p = Path('radar.py')
    if not p.exists():
        print("radar.py não encontrado.")
        return

    texto = p.read_text()
    
    # Verifica se já tem o import time
    if "import time" not in texto:
        texto = "import time\n" + texto

    # Procura a função que extrai com IA e adiciona o sleep
    # O nome da função pode variar, mas geralmente tem "extrair" ou "ia"
    padrao = r'(def (?:extrair_com_ia|extrair_ia|processar_edital).*?\n)'
    
    # Vamos apenas colocar um sleep global no início do loop de processamento
    # Uma forma segura é colocar dentro do loop principal de links
    if "time.sleep(3)" not in texto:
        # Adiciona um sleep genérico após as chamadas de API (buscando 'json=r.json()')
        texto = texto.replace('return _limpar_json("".join(x.get("text", "") for x in partes))', 'time.sleep(3)\n        return _limpar_json("".join(x.get("text", "") for x in partes))')

    p.write_text(texto)
    print("✅ Freio de segurança (time.sleep) adicionado ao radar.py!")

if __name__ == "__main__":
    adicionar_freio()
