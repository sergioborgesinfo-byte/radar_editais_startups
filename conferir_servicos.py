"""Confere credenciais e serviços antes da coleta, sem imprimir chaves."""
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def limpar_chave(valor):
    valor = (valor or "").strip()
    valor = re.sub(r"^(?:export\s+)?(?:TAVILY(?:_API_KEY)?|GEMINI(?:_API_KEY)?|ANTHROPIC_API_KEY)\s*=\s*", "", valor)
    if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in ("'", '"'):
        valor = valor[1:-1].strip()
    if not valor or any(c.isspace() for c in valor):
        raise ValueError("Chave vazia ou com espaços/quebras de linha")
    return valor


def consultar(nome, url, headers, corpo):
    for tentativa in range(3):
        req = Request(url, data=json.dumps(corpo).encode(),
                      headers={"Content-Type": "application/json", **headers}, method="POST")
        try:
            with urlopen(req, timeout=30) as resposta:
                dados = json.load(resposta)
            return dados
        except HTTPError as erro:
            codigo = erro.code
            erro.close()
            if codigo in (401, 403):
                raise RuntimeError(f"{nome}: acesso recusado (HTTP {codigo}). Confira o valor do secret no GitHub.") from None
            if codigo == 429 or 500 <= codigo <= 599:
                if tentativa < 2:
                    time.sleep(5 * (tentativa + 1))
                    continue
                raise RuntimeError(f"{nome}: serviço indisponível ou limite atingido (HTTP {codigo}). Tente novamente mais tarde.") from None
            raise RuntimeError(f"{nome}: falha HTTP {codigo}. Nenhuma coleta iniciada.") from None
        except (URLError, TimeoutError):
            if tentativa < 2:
                time.sleep(5 * (tentativa + 1))
                continue
            raise RuntimeError(f"{nome}: conexão indisponível. Nenhuma coleta iniciada.") from None


def main():
    nomes = ["TAVILY_API_KEY"]
    nomes += ["GEMINI_API_KEY"] if os.getenv("GEMINI_API_KEY") else ["ANTHROPIC_API_KEY"]
    for nome in nomes:
        try:
            os.environ[nome] = limpar_chave(os.getenv(nome))
        except ValueError as erro:
            raise RuntimeError(nome + ": " + str(erro)) from None
    consultar("Tavily", "https://api.tavily.com/search",
              {"Authorization": "Bearer " + os.environ["TAVILY_API_KEY"]},
              {"query": "edital startups Brasil", "max_results": 1, "search_depth": "basic"})
    print("Tavily: autenticação e consulta OK.")
    if "GEMINI_API_KEY" in nomes:
        modelo = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        consultar("Gemini", f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                  {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                  {"contents": [{"parts": [{"text": "Responda apenas OK."}]}], "generationConfig": {"maxOutputTokens": 32}})
        print("Gemini: autenticação e resposta OK.")
    else:
        consultar("Anthropic", "https://api.anthropic.com/v1/messages",
                  {"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                  {"model": os.getenv("RADAR_MODEL", "claude-haiku-4-5-20251001"), "max_tokens": 32,
                   "messages": [{"role": "user", "content": "Responda apenas OK."}]})
        print("Anthropic: autenticação e resposta OK.")
    destino = os.getenv("GITHUB_ENV")
    if destino:
        for nome in nomes:
            print("::add-mask::" + os.environ[nome])
        with open(destino, "a", encoding="utf-8") as arquivo:
            for nome in nomes:
                arquivo.write(nome + "=" + os.environ[nome] + "\n")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as erro:
        print("Verificação interrompida:", erro)
        raise SystemExit(1)
