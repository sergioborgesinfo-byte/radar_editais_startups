from pathlib import Path

def esconder_descobertas():
    p = Path('docs/index.html')
    if not p.exists():
        print("Arquivo index.html não encontrado.")
        return

    texto = p.read_text()

    if "esconder_descobertas_js" in texto:
        print("O botão já está escondido.")
        return

    js_script = """
  <script id="esconder_descobertas_js">
    document.addEventListener("DOMContentLoaded", function() {
        // Esconde o botão "Acompanhar descobertas" para não confundir o usuário final
        var botoes = document.querySelectorAll('a, button');
        for (var i = 0; i < botoes.length; i++) {
            if (botoes[i].innerText.includes('Acompanhar descobertas') || botoes[i].innerText.includes('Acompanhar Descobertas')) {
                botoes[i].style.display = 'none';
            }
        }
    });
  </script>
</body>"""

    if "</body>" in texto:
        texto = texto.replace("</body>", js_script)
        p.write_text(texto)
        print("✅ Botão escondido com sucesso no index.html!")
    else:
        print("❌ Tag </body> não encontrada.")

if __name__ == "__main__":
    esconder_descobertas()
