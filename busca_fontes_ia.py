"""Busca fontes com a mesma chave Gemini; respostas da busca não provam vigência."""
import json
import os
import re
from pathlib import Path
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.parse import urlsplit


def links_citados(resposta, resolver, oficial):
    encontrados=[]
    for candidato in resposta.get('candidates',[]):
        for item in candidato.get('groundingMetadata',{}).get('groundingChunks',[]):
            url=item.get('web',{}).get('uri','')
            p=urlsplit(url)
            if p.scheme != 'https' or p.username or p.password:continue
            if p.hostname == 'vertexaisearch.cloud.google.com':
                try:url=resolver(url)
                except Exception:continue
            p=urlsplit(url)
            if p.scheme in ('https','http') and not p.username and not p.password and oficial(url):
                if url not in encontrados:encontrados.append(url)
    return encontrados[:4]


class BuscaFontes:
    def __init__(self, limite=2, chamar=None, resolver=None, caminho='data/cache-busca-fontes.json'):
        self.limite=limite;self.chamadas=0;self.erros=[];self.parada=None
        self.chamar=chamar or self.api;self.resolver=resolver or self.redirecionar
        self.path=Path(caminho)
        try:self.cache=json.loads(self.path.read_text())
        except (OSError,ValueError):self.cache={}
        pausa=self.cache.get('__pausa__',{}).get('ate')
        if pausa:
            try:
                if datetime.now().astimezone()<datetime.fromisoformat(pausa):self.parada='busca_cota_em_pausa'
            except (ValueError,TypeError):pass

    def redirecionar(self,url):
        with urlopen(Request(url,headers={'User-Agent':'Radar-startups'}),timeout=15) as r:return r.url

    def api(self,registro):
        titulo=registro.get('dados',{}).get('titulo') or registro.get('titulo','')
        prompt=('Use Google Search para localizar a página oficial e o edital/cronograma desta oportunidade: '
                +json.dumps({'titulo':titulo,'url':registro['url']},ensure_ascii=False)
                +'. Procure a MESMA edição, ano e região. Não substitua por outra edição. '
                 'Cite as fontes oficiais encontradas. Não determine se está aberta; não invente URLs.')
        corpo={'contents':[{'parts':[{'text':prompt}]}],'tools':[{'google_search':{}}],
               'generationConfig':{'temperature':0,'maxOutputTokens':2000}}
        # Gemini 2.5 possui busca na cota gratuita; não usar modelos 3.x aqui.
        req=Request('https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
                    data=json.dumps(corpo).encode(),headers={'Content-Type':'application/json',
                    'x-goog-api-key':os.environ['GEMINI_API_KEY']})
        with urlopen(req,timeout=60) as r:return json.load(r)

    def buscar(self,registro,oficial,agora):
        url=registro['url'];anterior=self.cache.get(url,{})
        if anterior.get('em') and agora-datetime.fromisoformat(anterior['em'])<timedelta(days=7):
            return [u for u in anterior.get('fontes',[]) if oficial(u)]
        if self.parada or self.chamadas>=self.limite:return []
        self.chamadas+=1
        try:
            fontes=links_citados(self.chamar(registro),self.resolver,oficial)
            self.cache[url]={'em':agora.isoformat(),'fontes':fontes}
        except Exception as erro:
            codigo=getattr(erro,'code',None)
            self.erros.append({'tipo':type(erro).__name__,'codigo':codigo})
            if codigo in (401,403,404,429):self.parada='busca_http_'+str(codigo)
            if codigo==429:self.cache['__pausa__']={'ate':(agora+timedelta(hours=6)).isoformat()}
            self.cache[url]={'em':(agora-timedelta(days=6)).isoformat(),'fontes':[]}
            print('Busca de fontes falhou: '+type(erro).__name__+' '+str(codigo),flush=True)
            if hasattr(erro,'close'):erro.close()
            fontes=[]
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(json.dumps(self.cache,ensure_ascii=False,indent=2)+'\n')
        return fontes

    def ordem(self,registro):
        return self.cache.get(registro['url'],{}).get('em','')
