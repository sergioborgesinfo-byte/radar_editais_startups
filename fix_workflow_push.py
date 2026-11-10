from pathlib import Path

def ajustar_workflow():
    p = Path('.github/workflows/atualizar.yml')
    if not p.exists():
        print("Arquivo atualizar.yml não encontrado.")
        return

    texto = p.read_text()
    # Garante a permissão de escrita no topo do arquivo
    if "permissions:" not in texto:
        texto = "permissions:\n  contents: write\n\n" + texto
    elif "contents: write" not in texto:
        texto = texto.replace("permissions:", "permissions:\n  contents: write")

    # Substitui a etapa de push por uma versão mais robusta com pull --rebase
    bloco_antigo = """      - name: Salvar somente descobertas
        run: |
          git config user.name "$GITHUB_ACTOR"
          git config user.email "${{ github.actor_id }}+$GITHUB_ACTOR@users.noreply.github.com"
          git add data/oportunidades-descobertas.json data/descobertas.md
          if ! git diff --cached --quiet; then
            git commit -m "Atualiza candidatos descobertos; vigência não verificada"
            git pull --rebase origin "$GITHUB_REF_NAME"
            git push origin "HEAD:${GITHUB_REF_NAME}"
          fi"""
    
    bloco_novo = """      - name: Salvar estado e publicação
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add radar.db docs/editais.json data/
          if ! git diff --cached --quiet; then
            git commit -m "🤖 Robô: Atualização automática de editais"
            git pull --rebase origin "$GITHUB_REF_NAME"
            git push origin "HEAD:${GITHUB_REF_NAME}"
          fi"""

    if bloco_antigo in texto:
        texto = texto.replace(bloco_antigo, bloco_novo)
        p.write_text(texto)
        print("✅ Workflow ajustado com permissões e pull --rebase!")
    else:
        print("⚠️ Bloco antigo não encontrado. O arquivo pode já ter sido alterado.")

if __name__ == "__main__":
    ajustar_workflow()
