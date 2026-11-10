from pathlib import Path

def esconder_botao_exemplos():
    p = Path('docs/index.html')
    if not p.exists():
        print("Arquivo index.html não encontrado.")
        return

    texto = p.read_text()

    if "esconder_exemplos_js" in texto:
        print("O botão já está escondido.")
        return

    js_script = """
  <script id="esconder_exemplos_js">
    document.addEventListener("DOMContentLoaded", function() {
        var btnRst = document.getElementById('rst');
        if (btnRst) {
            btnRst.style.display = 'none';
        }
    });
  </script>
</body>"""

    if "</body>" in texto:
        texto = texto.replace("</body>", js_script)
        p.write_text(texto)
        print("✅ Botão 'Voltar aos exemplos' escondido com sucesso!")
    else:
        print("❌ Tag </body> não encontrada.")

if __name__ == "__main__":
    esconder_botao_exemplos()
