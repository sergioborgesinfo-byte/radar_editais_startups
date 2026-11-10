from pathlib import Path

def aplicar_filtro_exportador():
    p = Path('exportar_manual.py')
    if not p.exists():
        print("Arquivo exportar_manual.py não encontrado.")
        return

    texto = p.read_text()
    
    if "ano_antigo_detectado" in texto:
        print("O filtro já está ativo no exportador.")
        return

    funcao_filtro = """
def ano_antigo_detectado(e):
    texto_completo = f"{e.get('titulo','')} {e.get('url','')} {e.get('descricao','')} {e.get('requisitos','')} {e.get('trecho_prazo','')}".lower()
    anos_antigos = ['2020', '2021', '2022', '2023', '2024', '2025']
    for ano in anos_antigos:
        if ano in texto_completo:
            return True
    return False
"""

    texto = texto.replace("def exportar():", funcao_filtro + "\ndef exportar():")
    texto = texto.replace("    for e in rows:", "    for e in rows:\n        if ano_antigo_detectado(dict(e)):\n            continue")

    p.write_text(texto)
    print("✅ Filtro anti-fantasma adicionado ao exportar_manual.py!")

if __name__ == "__main__":
    aplicar_filtro_exportador()
