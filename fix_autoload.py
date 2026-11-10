from pathlib import Path

def adicionar_autoload():
    p = Path('docs/index.html')
    if not p.exists():
        print("index.html não encontrado.")
        return
        
    texto = p.read_text()
    
    # Se já foi modificado, não faz de novo
    if "Carregamento automático" in texto:
        print("O carregamento automático já está ativo.")
        return

    script_autoload = """
  <script>
    // Carregamento automático do JSON no Vercel/Servidor
    document.addEventListener("DOMContentLoaded", function() {
        fetch('editais.json')
            .then(response => {
                if (!response.ok) throw new Error("HTTP " + response.status);
                return response.json();
            })
            .then(arr => {
                if (Array.isArray(arr) && arr.length > 0) {
                    console.log("Editais carregados automaticamente!");
                    setData(arr, "Dados reais atualizados automaticamente", false);
                    // Salva no cache local como backup
                    try {
                        localStorage.setItem("radar-dados", JSON.stringify({nome: "editais.json", dados: arr}));
                    } catch(e) {}
                }
            })
            .catch(err => {
                console.log("Aviso: Não foi possível carregar os editais automaticamente. Usando dados locais ou demo.", err);
            });
    });
  </script>
</body>"""

    # Substitui a tag de fechamento do body pelo script + fechamento
    if "</body>" in texto:
        texto = texto.replace("</body>", script_autoload)
        p.write_text(texto)
        print("✅ Carregamento automático adicionado com sucesso ao index.html!")
    else:
        print("❌ Tag </body> não encontrada no arquivo.")

if __name__ == "__main__":
    adicionar_autoload()
