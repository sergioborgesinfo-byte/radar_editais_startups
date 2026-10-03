# Auditoria e nova rota do Radar Startups

Revisão em 03/10/2026. Referência antes da mudança: 561 registros de conteúdo;
100 confirmados na relevância; 122 pendentes por cota de IA; 254 pendentes de
leitura. Na vigência: 145 registros históricos, 50 pendentes no total e 46 na
fila inicial de 78. Publicação: 9 oportunidades abertas.

## Diagnóstico por mecanismo

| Mecanismo | Evidência encontrada | Decisão aplicada |
|---|---|---|
| Descoberta | 71/142 consultas concluídas; HTTP 432 repetido nas restantes | Lotes rotativos de até 24 consultas; interromper cota/credencial sem repetir cada consulta; preservar o catálogo existente |
| Triagem | Windows, concurso escolar e seleção de bolsista entraram na vigência | Excluir esses públicos explicitamente; manter a decisão e motivo para auditoria |
| Relevância | 122 registros em 429; leitor diferente do de vigência; bloqueio permanente após três falhas | Retomar a etapa a cada rodada, usar o mesmo leitor, cachear resposta pela entrada e registrar próxima tentativa |
| Qualidade | A contagem de tentativas liberava ou bloqueava globalmente as oportunidades | Liberar cada registro comprovado; cobertura permanece uma métrica, sem impedir o restante da fila |
| Fontes primárias | Arquivos e triggers citavam busca Gemini que não está presente no código atual | Pesquisa Tavily limitada a quatro casos sem documentos/acesso; só candidatos compatíveis de fonte reconhecida; o prazo continua dependendo da leitura do documento |
| Vigência | Espera de 24 h mesmo depois de mudar a fonte; mesma resposta podia ser solicitada novamente por metadados | Retentativa em 15 min para rede, seis horas para evidência insuficiente; troca de fonte libera tentativa; hash usa identidade e documentos, sem horário de registro |
| IA | Limites separados por etapa e até três lotes multiplicavam o consumo | Orçamento global de oito chamadas, incluindo retentativas; relevância usa no máximo três; cota gera pausa compartilhada de seis horas |
| Persistência | Um commit gravou saída truncada como JSON e impediu a execução | Recuperação pelo Git já aplicada; nova escrita atômica com validação e substituição de arquivo |
| Agendamento | Quatro workflows encadeados e grupos de concorrência diferentes | Uma rodada integrada por hora; descoberta diária aciona a mesma rodada; todos os escritores automáticos compartilham o grupo de concorrência |
| Publicação | Painel combinava arquivos de atualizações diferentes e dizia apenas “concluído” | Uma fotografia conjunta; casos concluídos/reabertos, saldo de abertas, último avanço e bloqueio externo; atualização da página a cada minuto |

## Rota operacional

1. Triar o catálogo preservado e descartar conteúdo explicitamente fora do público.
2. Retomar a relevância em lotes, preservando os resultados anteriores e a cota de vigência.
3. Pesquisar fontes dos casos sem documento útil ou com acesso indisponível.
4. Validar regras/datas nos documentos e recorrer à IA com citações verificáveis.
5. Gravar o estado íntegro, exportar abertas e informar o avanço da rodada.

Arquivos de implementação: `executar_pipeline.py`, `estado_pipeline.py`,
`pesquisar_fontes.py` e as etapas existentes. A rotina automática principal
continua em `.github/workflows/vigencia.yml`. Os antigos workflows de conteúdo
e triagem ficam disponíveis apenas para disparo manual, sem cadeia automática.

## Critérios de aceitação

- Nenhuma chamada além do orçamento global; retentativas contam como chamadas.
- Ausência de documento aciona descoberta de fonte, em vez de prompt sem prova.
- Metadados de registro não invalidam a interpretação de um documento igual.
- Falha de escrita não substitui o arquivo anterior por conteúdo incompleto.
- Outra edição, outro estado ou domínio não reconhecido não fornecem a data.
- Encerramento, exclusão por escopo e nova abertura aparecem separadamente.
- Rodada sem mudança informa ausência de avanço; horário de gravação não vira progresso.

## Limites e próximas decisões

O HTTP 432 da busca externa precisa ser medido na chamada real da nova rodada.
Caso persista, a descoberta fica em pausa: mudar o leitor ou o prompt não
reconstitui a cota do fornecedor. O app continua validando o catálogo e os
documentos disponíveis. A política de domínios reconhecidos ainda combina
catálogo e regras amplas de domínio; não equivale a prova de autoria de toda
página e merece substituição por um cadastro de instituições e programas.

PDF digitalizado sem camada de texto ainda precisa de OCR. O navegador só
resolve renderização: não contorna bloqueios de acesso e não comprova o prazo.
As páginas de fluxo contínuo são reconferidas em 24 h; oportunidades datadas,
em 48 h. Falha de renovação pode retirar uma ficha da publicação, para evitar
continuar exibindo informação sem confirmação atual.

Após essa execução, a avaliação deve usar o relatório `data/execucao-pipeline.json`:
novos casos concluídos por resultado, chamadas por etapa, fontes recuperadas,
reaberturas e saldo de abertas. Testes aprovados não substituem essa medição.
