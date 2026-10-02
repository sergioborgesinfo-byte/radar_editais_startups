"""Reutiliza downloads públicos por seis horas, sem cachear falhas."""
import base64
import gzip
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from functools import lru_cache

def leitor_cache(baixar, pasta='.radar-leituras', ttl=21600):
    raiz=Path(pasta)
    @lru_cache(maxsize=128)
    def ler(url):
        caminho=raiz/(hashlib.sha256(url.encode()).hexdigest()+'.json.gz')
        try:
            d=json.loads(gzip.decompress(caminho.read_bytes()))
            if 0 <= time.time()-d['em'] < ttl:
                return d['tipo'],base64.b64decode(d['dados'],validate=True)
        except (OSError,ValueError,KeyError,TypeError):pass
        tipo,bruto=baixar(url)
        if bruto is not None:
            raiz.mkdir(parents=True,exist_ok=True)
            tmp=caminho.with_name(caminho.name+'.'+uuid.uuid4().hex+'.tmp')
            d={'em':time.time(),'tipo':tipo,'dados':base64.b64encode(bruto).decode()}
            tmp.write_bytes(gzip.compress(json.dumps(d).encode()));os.replace(tmp,caminho)
        return tipo,bruto
    return ler
