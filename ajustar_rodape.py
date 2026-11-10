from pathlib import Path
import re

def ajustar_rodape():
    p = Path('docs/index.html')
    if not p.exists():
        print("Arquivo index.html não encontrado.")
        return

    texto = p.read_text()

    # Novo bloco de rodapé, mais fino e elegante
    novo_rodape = """<style>
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
</body>"""

    # Substitui todo o bloco antigo do rodapé pelo novo
    padrao = r'<style>.*?id="credit-footer".*?</footer>\s*</body>'
    
    if re.search(padrao, texto, re.DOTALL):
        texto = re.sub(padrao, novo_rodape, texto, flags=re.DOTALL)
        p.write_text(texto)
        print("✅ Rodapé ajustado e mais fino com sucesso!")
    else:
        print("❌ Não foi possível encontrar o bloco antigo do rodapé.")

if __name__ == "__main__":
    ajustar_rodape()
