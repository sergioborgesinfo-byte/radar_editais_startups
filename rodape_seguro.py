from pathlib import Path

def adicionar_rodape_seguro():
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
        padding: 1rem 1rem 0.8rem;
        margin-top: 1.5rem;
        color: #8892a0;
        font-size: 0.75rem;
        border-top: 1px solid #eaeaea;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .credit-footer strong {
        color: #343a40;
        font-weight: 600;
    }
    .credit-footer .sub {
        font-size: 0.65rem;
        margin-top: 0.2rem;
        opacity: 0.7;
    }
  </style>
  <footer class="credit-footer" id="credit-footer">
      <div>Desenvolvido por <strong>Sérgio Luiz Xavier Borges</strong></div>
      <div class="sub">Radar de Editais para Startups &copy; 2026</div>
  </footer>
"""

    # Acha a ÚLTIMA ocorrência da tag de fechamento do body
    posicao = texto.rfind("</body>")
    
    if posicao != -1:
        # Corta o texto, insere o rodapé e junta tudo de novo
        novo_texto = texto[:posicao] + rodape_html + texto[posicao:]
        p.write_text(novo_texto)
        print("✅ Rodapé adicionado com segurança!")
    else:
        print("❌ Tag </body> não encontrada.")

if __name__ == "__main__":
    adicionar_rodape_seguro()
