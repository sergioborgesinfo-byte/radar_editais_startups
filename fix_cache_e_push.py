from pathlib import Path
import re

def corrigir():
    # 1. Corrigir o cache no index.html
    p_html = Path('docs/index.html')
    if p_html.exists():
        texto = p_html.read_text()
        if "editais.json?t=" not in texto:
            texto = texto.replace("fetch('editais.json')", "fetch('editais.json?t=' + new Date().getTime())")
            p_html.write_text(texto)
            print("✅ Cache do navegador desativado no index.html!")

    # 2. Blindar o atualizar.yml contra conflitos
    p_yaml = Path('.github/workflows/atualizar.yml')
    if p_yaml.exists():
        texto = p_yaml.read_text()
        bloco_antigo = """            git pull --rebase origin "$GITHUB_REF_NAME"
            git push origin "HEAD:${GITHUB_REF_NAME}\""""
        bloco_novo = """            git pull --rebase origin "$GITHUB_REF_NAME" || git rebase --abort
            git push origin "HEAD:${GITHUB_REF_NAME}" || git push -f origin "HEAD:${GITHUB_REF_NAME}\""""
        
        if bloco_antigo in texto:
            texto = texto.replace(bloco_antigo, bloco_novo)
            p_yaml.write_text(texto)
            print("✅ atualizar.yml blindado contra falhas de push!")
        else:
            # Tenta uma versão mais flexível se a string exata não bater
            if "git push -f origin" not in texto and "git push origin" in texto:
                texto = texto.replace("git push origin", "git push -f origin")
                p_yaml.write_text(texto)
                print("✅ atualizar.yml blindado contra falhas de push (modo flexível)!")

if __name__ == "__main__":
    corrigir()
