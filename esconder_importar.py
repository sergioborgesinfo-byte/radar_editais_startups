from pathlib import Path

def esconder_botao_importar():
    p = Path('docs/index.html')
    if not p.exists():
        print("Arquivo index.html não encontrado.")
        return

    texto = p.read_text()

    if "esconder_importar_js" in texto:
        print("O botão já está escondido.")
        return

    js_script = """
  <script id="esconder_importar_js">
    document.addEventListener("DOMContentLoaded", function() {
        var btnImp = document.getElementById('imp');
        if (btnImp) {
            btnImp.style.display = 'none';
        }
    });
  </script>
</body>"""

    if "</body>" in texto:
        texto = texto.replace("</body>", js_script)
        p.write_text(texto)
        print("✅ Botão 'Importar editais.json' escondido com sucesso!")
    else:
        print("❌ Tag </body> não encontrada.")

if __name__ == "__main__":
    esconder_botao_importar()
