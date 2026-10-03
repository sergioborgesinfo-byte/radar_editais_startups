# Radar de editais (PWA)

O fluxo automático atual é `python executar_pipeline.py`: triagem, relevância,
pesquisa de fontes e vigência, com orçamento compartilhado de oito chamadas de
IA por execução. `GEMINI_API_KEY` interpreta os documentos; `TAVILY_API_KEY`
pesquisa fontes faltantes. A descoberta ampla roda separadamente, em lotes
rotativos, sem descartar o histórico.

O diagnóstico e as decisões da revisão estão em [AUDITORIA_RADAR.md](AUDITORIA_RADAR.md).
`data/execucao-pipeline.json` registra avanço real, cota e resultados por etapa.
Uma execução concluída pode não resolver novos casos; o painel informa isso.
O fluxo legado `radar.py run` abaixo não é a rotina de publicação atual.

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
