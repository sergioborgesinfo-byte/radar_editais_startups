from pathlib import Path

def pausar():
    # Pausa o atualizar.yml
    p = Path('.github/workflows/atualizar.yml')
    if p.exists():
        texto = p.read_text()
        if "workflow_dispatch:" in texto:
            texto = texto.replace("workflow_dispatch:", "workflow_dispatch:\n  # Desativado temporariamente\n  if: false")
            p.write_text(texto)
            print("✅ Robô da nuvem pausado temporariamente.")

if __name__ == "__main__":
    pausar()
