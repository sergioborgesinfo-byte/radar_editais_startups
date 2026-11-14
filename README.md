# Radar de editais para startups (PWA)

Aplicação web progressiva (PWA) e pipeline automatizado para descoberta, validação e publicação de editais de fomento, subvenção, incubação e aceleração para startups no Brasil.

## Fluxo Automático Oficial (GitHub Actions)

O workflow principal (`.github/workflows/atualizar.yml`) roda automaticamente 4 vezes ao dia (`06h, 12h, 18h e 23h UTC`) executando:

1. **Coleta e extração com IA (`python radar.py run`):** Lê as fontes ativas de `sources.json` e a fila de descobertas (`data/oportunidades-descobertas.json`), baixa páginas e PDFs respeitando o `robots.txt`, extrai informações estruturadas com IA (`GEMINI_API_KEY` ou `ANTHROPIC_API_KEY`), pesquisa fontes com `TAVILY_API_KEY` e persiste no banco SQLite `radar.db`.
2. **Resgate de prazos (`python resgatar_pendencias.py`):** Analisa os trechos literais de inscrição (`trecho_prazo`) de editais pendentes para recuperar datas válidas que a IA não converteu diretamente para o formato ISO.
3. **Exportação e filtro de vigência (`python exportar_manual.py`):** Filtra editais vencidos, bloqueia falsos positivos de fluxo contínuo, deduplica chamadas equivalentes e gera o arquivo final `docs/editais.json` consumido pelo site na Vercel.

*(Nota: O fluxo alternativo em estágios `executar_pipeline.py` e o histórico da auditoria estão documentados em [AUDITORIA_RADAR.md](AUDITORIA_RADAR.md) e permanecem disponíveis para execução manual).*

## Estrutura Principal

- `radar.py`, `radar_automacao.py`, `sources.json`: Coleta, extração com IA e validação de evidências no SQLite.
- `resgatar_pendencias.py`, `exportar_manual.py`: Recuperação de datas em `trecho_prazo`, filtro de vigência e geração do JSON de produção.
- `radar.db`: Banco de dados SQLite principal na raiz do projeto.
- `docs/`: Aplicativo PWA estático (`index.html`, `acompanhamento.js`, `manifest.json`, `sw.js`, `icons/`) e o `editais.json` publicado.
- `data/`: Catálogos de descoberta, caches e relatórios de auditoria.
- `testes_*.py`: Suíte de 165 testes unitários automatizados.

## Como rodar no computador

1. Crie e ative o ambiente virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Configure as chaves de API no arquivo `.env` (ou variáveis de ambiente): `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` e `TAVILY_API_KEY`.
3. Execute o ciclo completo de atualização:
   ```bash
   python radar.py run
   python resgatar_pendencias.py
   python exportar_manual.py
   ```
4. Para testar o site localmente:
   ```bash
   cd docs && python -m http.server 8000
   ```
   Abra `http://localhost:8000` no navegador.
5. Para rodar a suíte de testes:
   ```bash
   python -m unittest discover -s . -p 'testes_*.py'
   ```
