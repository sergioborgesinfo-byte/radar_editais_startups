from pathlib import Path

def bloquear_antigos():
    p = Path('radar.py')
    if not p.exists():
        print("radar.py não encontrado.")
        return

    texto = p.read_text()

    if "filtro_ano_antigo" in texto:
        print("O filtro já está ativo.")
        return

    # Código que verifica se o título ou link tem anos antigos (2022, 2023, 2024)
    filtro = """
# filtro_ano_antigo: Bloqueia editais de anos anteriores para evitar alucinação da IA
import datetime
ano_atual = datetime.datetime.now().year
anos_antigos = [str(ano_atual - i) for i in range(1, 5)] # Pega 2025, 2024, 2023, 2022 (se atual for 2026)

def e_antigo(titulo, url):
    texto_alvo = f"{titulo or ''} {url or ''}"
    for ano in anos_antigos:
        if ano in texto_alvo:
            return True
    return False
"""

    # Injeta o filtro logo após os imports
    texto = filtro + "\n" + texto

    # Procura a função que extrai os dados e adiciona o bloqueio
    if "def _limpar_json" in texto:
        texto = texto.replace(
            "def _limpar_json", 
            "# Verifica se é antigo antes de processar\ntry:\n    if e_antigo(d.get('titulo'), url): return None\nexcept: pass\n\ndef _limpar_json"
        )

    p.write_text(texto)
    print("✅ Filtro de anos antigos (2022-2025) adicionado ao radar.py!")

if __name__ == "__main__":
    bloquear_antigos()
