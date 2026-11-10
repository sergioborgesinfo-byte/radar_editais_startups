from pathlib import Path
import re

def atualizar_filtro():
    p = Path('exportar_manual.py')
    if not p.exists():
        print("exportar_manual.py não encontrado.")
        return

    texto = p.read_text()

    # Remove o filtro antigo (burro) se ele existir
    padrao_antigo = r'def ano_antigo_detectado\(e\):.*?return False'
    texto = re.sub(padrao_antigo, '', texto, flags=re.DOTALL)

    # Adiciona o novo filtro inteligente
    novo_filtro = """
def ano_antigo_detectado(e):
    texto_completo = f"{e.get('titulo','')} {e.get('url','')} {e.get('descricao','')} {e.get('requisitos','')} {e.get('trecho_prazo','')}".lower()
    
    # 1. Se for fluxo contínuo, NUNCA é fantasma (mesmo se for de 2020)
    if "fluxo contínuo" in texto_completo or "fluxo continuo" in texto_completo or "sem data final" in texto_completo:
        return False
        
    # 2. Se tiver data de encerramento e for de anos antigos, é fantasma
    anos_antigos = ['2020', '2021', '2022', '2023', '2024', '2025']
    for ano in anos_antigos:
        if ano in texto_completo:
            return True
    return False
"""

    # Insere o novo filtro antes da função exportar
    texto = texto.replace("def exportar():", novo_filtro + "\ndef exportar():")
    
    # Garante que a checagem no loop está correta
    if "if ano_antigo_detectado" not in texto:
        texto = texto.replace("    for e in rows:", "    for e in rows:\n        if ano_antigo_detectado(dict(e)):\n            continue")

    p.write_text(texto)
    print("✅ Filtro inteligente (que preserva fluxo contínuo antigo) aplicado!")

if __name__ == "__main__":
    atualizar_filtro()
