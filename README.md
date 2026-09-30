# Radar de editais (PWA)

## Estrutura
- `radar.py`, `sources.json`, `requirements.txt`: coleta e extração com IA
- `data/radar.db`: banco (criado na primeira execução)
- `docs/`: o aplicativo (index.html, manifest.json, sw.js, icons/) e o `editais.json` gerado
- `.github/workflows/atualizar.yml`: coleta diária automática

## Rodar no computador
1. `python -m venv .venv` e ative o ambiente
2. `pip install -r requirements.txt`
3. defina `ANTHROPIC_API_KEY`
4. edite `sources.json` (fontes reais, `"ativo": true`) e o e-mail em `UA` no `radar.py`
5. `python radar.py run`
6. `python radar.py export --saida docs/editais.json`
7. `cd docs && python -m http.server 8000` e abra http://localhost:8000
