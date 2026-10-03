"""Uma rodada, um orçamento e um relatório de avanço para todas as etapas."""
import json
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import estado_pipeline
from estado_pipeline import salvar_json


def ler(caminho, padrao):
    try: return json.loads(Path(caminho).read_text())
    except (OSError, ValueError): return padrao


def fotografar():
    conteudo = ler('data/oportunidades-conteudo.json', {'itens': []})
    vigencia = ler('data/oportunidades-vigencia.json', {'itens': []})
    itens = vigencia['itens']
    return {'conteudo': dict(Counter(e['status'] for e in conteudo['itens'])),
            'vigencia': dict(Counter(e['status'] for e in itens)),
            'situacoes': {e['url']: e['status'] for e in itens},
            'abertas_publicadas': len(ler('docs/editais.json', [])),
            'fila_inicial': vigencia.get('fila_prioritaria', {})}


def progresso(antes, depois):
    definitivos = {'aberta_confirmada', 'encerrada', 'ainda_nao_aberta', 'fora_escopo'}
    novos = [u for u, s in depois['situacoes'].items() if s in definitivos
             and antes['situacoes'].get(u) not in definitivos]
    regressao = [u for u, s in antes['situacoes'].items() if s in definitivos
                 and depois['situacoes'].get(u) not in definitivos]
    return {'casos_concluidos_nesta_rodada': len(novos),
            'concluidos_por_resultado': dict(Counter(depois['situacoes'][u] for u in novos)),
            'casos_reabertos': len(regressao),
            'saldo_abertas': depois['abertas_publicadas'] - antes['abertas_publicadas']}


def main():
    inicio = datetime.now(timezone.utc)
    anterior = ler('data/execucao-pipeline.json', {})
    antes = fotografar()
    estado_pipeline.orcamento = estado_pipeline.Orcamento(int(os.getenv('RADAR_IA_LIMITE', '8')))
    # Garante espaço à verificação de vigência em vez de gastar toda a cota na entrada.
    estado_pipeline.orcamento.limites_etapa['conteudo'] = 3
    etapas = []
    relatorio = {'iniciada_em': inicio.isoformat(), 'status': 'em_execucao', 'etapas': etapas}
    salvar_json('data/execucao-pipeline.json', relatorio)
    from triar_descobertas import main as triar
    from confirmar_oportunidades import main as confirmar
    from pesquisar_fontes import executar as pesquisar, catalogar
    from validar_vigencia import main as validar
    # Uma cadeia única substitui workflows concorrentes escrevendo os mesmos arquivos.
    for nome, tarefa in [('catalogos', catalogar), ('triagem', triar), ('conteudo', confirmar), ('fontes', pesquisar), ('vigencia', validar)]:
        duracao = time.monotonic()
        etapa = {'nome': nome}
        try:
            resultado = tarefa()
            etapa.update(status='concluida', resultado=resultado)
        except (Exception, SystemExit) as erro:
            etapa.update(status='falha', tipo=type(erro).__name__)
            print('Etapa falhou: ' + nome + ' (' + type(erro).__name__ + ')', flush=True)
        etapa['segundos'] = round(time.monotonic() - duracao, 1)
        etapas.append(etapa)
        salvar_json('data/execucao-pipeline.json', relatorio)
    depois = fotografar()
    delta = progresso(antes, depois)
    fim = datetime.now(timezone.utc)
    ia = estado_pipeline.orcamento
    mudou = delta['casos_concluidos_nesta_rodada'] or delta['saldo_abertas'] or delta['casos_reabertos']
    relatorio.update(delta, finalizada_em=fim.isoformat(),
        status='falha_parcial' if any(e['status'] == 'falha' for e in etapas) else 'concluida',
        houve_avanco=bool(mudou), ultimo_avanco_em=fim.isoformat() if mudou else anterior.get('ultimo_avanco_em'),
        ia={'chamadas': ia.usadas, 'limite': ia.limite, 'por_etapa': ia.por_etapa, 'bloqueio': ia.motivo()},
        contagem=depois,
        motivo_sem_avanco=None if mudou else ('gemini_cota_em_pausa' if ia.motivo() == 'gemini_cota_em_pausa'
                           else 'aguardando_nova_evidencia_ou_proxima_tentativa'))
    relatorio['contagem'].pop('situacoes', None)
    salvar_json('data/execucao-pipeline.json', relatorio)
    painel = ler('docs/busca.json', {})
    painel['pipeline'] = relatorio
    # Usa uma única fotografia para os contadores de conteúdo e vigência.
    conteudo = ler('data/oportunidades-conteudo.json', {'itens': []})
    painel['confirmacoes'] = conteudo['itens']
    painel['atualizado_em'] = conteudo.get('atualizado_em', fim.isoformat())
    triagem = ler('data/triagem-descobertas.json', {})
    painel['itens'] = triagem.get('itens', painel.get('itens', []))
    painel['links'] = triagem.get('links_recebidos', painel.get('links', 0))
    painel['candidatos'] = triagem.get('contagem', {}).get('prioridade_verificacao', 0)
    salvar_json('docs/busca.json', painel)
    resumo = '\n## Rodada do Radar\n\n' + json.dumps({k:v for k,v in relatorio.items() if k not in ('contagem','etapas')}, ensure_ascii=False) + '\n'
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as arquivo: arquivo.write(resumo)
    print(resumo, flush=True)
    if relatorio['status'] == 'falha_parcial': raise SystemExit(1)


if __name__ == '__main__': main()
