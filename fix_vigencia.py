from pathlib import Path
import re

def corrigir_vigencia():
    p = Path('.github/workflows/vigencia.yml')
    if not p.exists():
        print("Arquivo vigencia.yml não encontrado.")
        return

    texto = p.read_text()

    # 1. Garantir a permissão de escrita
    if "permissions:" not in texto:
        texto = "permissions:\n  contents: write\n\n" + texto
    elif "contents: write" not in texto:
        texto = texto.replace("permissions:", "permissions:\n  contents: write")

    # 2. Substituir o bloco de salvamento por um mais seguro
    bloco_antigo = """      - name: Salvar estado e publicação
        if: always()
        run: |
          git config user.name "$GITHUB_ACTOR"
          git config user.email "${{ github.actor_id }}+$GITHUB_ACTOR@users.noreply.github.com"
          git add data docs/busca.json docs/editais.json
          if ! git diff --cached --quiet; then
            git commit -m "Salva rodada integrada, evidências e avanço real do Radar"
            git pull --rebase origin main
            git push origin HEAD:main
          fi"""

    bloco_novo = """      - name: Salvar estado e publicação
        if: always()
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          if ! git diff --cached --quiet; then
            git commit -m "Salva rodada integrada, evidências e avanço real do Radar"
            git pull --rebase origin main || git rebase --abort
            git push origin HEAD:main
          fi"""

    if bloco_antigo in texto:
        texto = texto.replace(bloco_antigo, bloco_novo)
        p.write_text(texto)
        print("✅ vigencia.yml corrigido com permissões e git seguro!")
    else:
        print("⚠️ Bloco antigo não encontrado. Verifique se o arquivo já foi alterado.")

if __name__ == "__main__":
    corrigir_vigencia()
