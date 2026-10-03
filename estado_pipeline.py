"""Gravação íntegra e orçamento compartilhado pelas etapas da mesma execução."""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


def salvar_json(caminho, dados):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    bruto = json.dumps(dados, ensure_ascii=False, indent=2) + '\n'
    json.loads(bruto)
    fd, temporario = tempfile.mkstemp(dir=caminho.parent, prefix=caminho.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as arquivo:
            arquivo.write(bruto)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, caminho)
    finally:
        if os.path.exists(temporario): os.unlink(temporario)


class Orcamento:
    def __init__(self, limite=8, caminho='data/estado-ia.json', agora=None):
        self.limite = limite
        self.usadas = 0
        self.por_etapa = {}
        self.limites_etapa = {}
        self.caminho = Path(caminho)
        self.agora = agora or datetime.now(timezone.utc)
        try: self.estado = json.loads(self.caminho.read_text())
        except (OSError, ValueError): self.estado = {}

    def motivo(self):
        try:
            if datetime.fromisoformat(self.estado['pausa_ate']) > self.agora:
                return 'gemini_cota_em_pausa'
        except (KeyError, ValueError, TypeError): pass
        return 'orcamento_execucao_esgotado' if self.usadas >= self.limite else None

    def reservar(self, etapa):
        motivo = self.motivo()
        if motivo: return motivo
        if self.por_etapa.get(etapa, 0) >= self.limites_etapa.get(etapa, self.limite):
            return 'orcamento_etapa_esgotado'
        self.usadas += 1
        self.por_etapa[etapa] = self.por_etapa.get(etapa, 0) + 1
        return None

    def pausar(self):
        self.estado['pausa_ate'] = (self.agora + timedelta(hours=6)).isoformat()
        salvar_json(self.caminho, self.estado)


orcamento = None


def reservar(etapa):
    return orcamento.reservar(etapa) if orcamento else None


def pausar():
    if orcamento: orcamento.pausar()
