from pathlib import Path

def adicionar_rodape():
    p = Path('docs/index.html')
    if not p.exists():
        print("Arquivo index.html não encontrado.")
        return

    texto = p.read_text()

    if "credit-footer" in texto:
        print("O rodapé já existe.")
        return

    rodape_html = """
  <style>
    .credit-footer {
        text-align: center;
        padding: 2.5rem 1rem 1.5rem;
        margin-top: 3rem;
        color: #6c757d;
        font-size: 0.9rem;
        border-top: 1px solid #eaeaea;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .credit-footer strong {
        color: #343a40;
    }
    .credit-footer .sub {
        font-size: 0.75rem;
        margin-top: 0.5rem;
        opacity: 0.8;
    }
  </style>
  <footer class="credit-footer" id="credit-footer">
      <p>Desenvolvido por <strong>Sérgio Luiz Xavier Borges</strong></p>
      <p class="sub">Radar de Editais para Startups &copy; 2026</p>
  </footer>
</body>"""

    if "</body>" in texto:
        texto = texto.replace("</body>", rodape_html)
        p.write_text(texto)
        print("✅ Rodapé com créditos adicionado com sucesso!")
    else:
        print("❌ Tag </body> não encontrada.")

if __name__ == "__main__":
    adicionar_rodape()
