from pathlib import Path
import re

def turbinar_buscas():
    arquivo = Path('descobrir_oportunidades.py')
    if not arquivo.exists():
        print("Arquivo descobrir_oportunidades.py não encontrado.")
        return

    texto = arquivo.read_text()
    
    # Lista turbinada de buscas na internet inteira
    novas_consultas = '''CONSULTAS = [
    "editais abertos startups fomento incubacao 2026",
    "chamada publica inovacao startups aceleracao inscricoes",
    "programa de incubacao startups fluxo continuo inscricoes abertas",
    "subvencao economica inovacao startups edital 2026",
    "CRITT UFJF incubacao startups edital",
    "PNCP editais inovacao startups",
    "Finep BNDES FAPESP FAPEMIG FAPESC editais startups 2026",
    "aceleradora startups Brasil inscricoes abertas",
    "premiacao startups inovacao edital 2026",
    "financiamento startups credito subvencao edital"
]'''

    # Tenta substituir a lista antiga de CONSULTAS
    if "CONSULTAS = [" in texto:
        texto = re.sub(r'CONSULTAS\s*=\s*\[.*?\]', novas_consultas, texto, flags=re.DOTALL)
    else:
        # Se não achar a variável, tenta achar a função de busca principal e injeta
        texto = novas_consultas + "\n\n" + texto

    arquivo.write_text(texto)
    print("✅ Buscas turbinadas com sucesso no descobrir_oportunidades.py!")

if __name__ == "__main__":
    turbinar_buscas()
