#!/usr/bin/env python3
"""Sincronizador direto com o painel Power BI do Radar de Oportunidades do CRITT/UFJF.

Extrai via API pública do Power BI (querydata) as oportunidades ativas voltadas para
Startups, MPEs e Empresas, filtra prazos já expirados, limpa redirecionadores de links,
classifica modalidade/estágio e grava no radar.db com verificação automática.
"""
import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, unquote, urlparse

import requests

import radar
from radar_automacao import SCHEMA as SCHEMA_AUTO, VERSAO, agora, normalizar

RESOURCE_KEY = "add569f8-dcfe-4dfc-8ac8-841c2b076b78"
MODEL_ID = 8025186
CLUSTERS = (
    "wabi-brazil-south-b-primary-api.analysis.windows.net",
    "wabi-brazil-south-api.analysis.windows.net",
)
COLUNAS = (
    "Oportunidade",
    "Instituição",
    "Prazo",
    "Acesso",
    "Status",
    "Perfil",
    "Fluxo Contínuo",
    "Objetivo",
    "Requisitos",
    "Benefícios",
    "Categoria de Apoio",
    "Instrumentos de Apoio",
)


def limpar_url(url_bruta):
    url = (url_bruta or "").strip()
    if not url:
        return ""
    # Desembrulha links do redirecionador do Google (https://www.google.com/url?q=...)
    if "google.com/url" in url:
        qs = parse_qs(urlparse(url).query)
        if "q" in qs and qs["q"]:
            url = unquote(qs["q"][0]).strip()
    # Remove parâmetros longos de rastreamento de anúncios (utm_*, gclid, hsa_*)
    if "utm_" in url or "gclid=" in url:
         url = url.split("?", 1)[0]
    return url


def interpretar_data_critt(prazo_val, continuo_val):
    """Converte datas do Power BI do CRITT (timestamp em ms ou string M/D/YYYY ou D/M/YYYY).
    Retorna (data_iso_ou_None, expirou_bool).
    """
    hoje_str = datetime.now().strftime("%Y-%m-%d")
    candidatos = [prazo_val, continuo_val]
    for valor in candidatos:
        if valor is None:
            continue
        if isinstance(valor, (int, float)) and valor > 100000000:
            dt = datetime.fromtimestamp(valor / 1000, tz=timezone.utc)
            iso = dt.strftime("%Y-%m-%d")
            # Datas de validade de patente na década de 2030+ são tratadas como oferta contínua
            if dt.year >= 2029:
                return None, False
            return iso, (iso < hoje_str)
        texto = str(valor).strip()
        if not texto or texto.upper() in ("NÃO INFORMADO", "NAO INFORMADO", "FLUXO CONTÍNUO", "FLUXO CONTINUO", "CONTÍNUO", "CONTINUO"):
            continue
        m_iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})", texto)
        if m_iso:
            iso = m_iso.group(0)
            if int(m_iso.group(1)) >= 2029:
                return None, False
            return iso, (iso < hoje_str)
        m_barra = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", texto)
        if m_barra:
            p1, p2, ano = int(m_barra.group(1)), int(m_barra.group(2)), int(m_barra.group(3))
            # No Power BI em inglês o formato padrão é M/D/YYYY
            mes, dia = (p1, p2) if p1 <= 12 else (p2, p1)
            try:
                dt = datetime(ano, mes, dia)
                iso = dt.strftime("%Y-%m-%d")
                if ano >= 2029:
                    return None, False
                return iso, (iso < hoje_str)
            except ValueError:
                pass
    return None, False


def classificar_tipo(item):
    texto = f"{item.get('Oportunidade','')} {item.get('Categoria de Apoio','')} {item.get('Instrumentos de Apoio','')} {item.get('Benefícios','')} {item.get('Objetivo','')}".lower()
    if re.search(r"subven[cç][aã]o|fomento n[aã]o reembols[aá]vel|recursos n[aã]o reembols[aá]veis|grant", texto):
        return "Subvenção"
    if re.search(r"cr[eé]dito|financiamento reembols[aá]vel|inovacred|fne |finame|microcr[eé]dito|procred", texto):
        return "Crédito"
    if re.search(r"incuba[cç][aã]o|pr[eé]-incuba|condom[ií]nio de empresas|crittworking|residente", texto):
        return "Incubação"
    if re.search(r"acelera[cç][aã]o|accelerator|venture capital|investimento|cvc|ventures", texto):
        return "Aceleração"
    if re.search(r"pr[eê]mio|premia[cç][aã]o|award", texto):
        return "Prêmio"
    if re.search(r"bolsa", texto):
        return "Bolsa"
    return "Inovação aberta"


def extrair_valor_reais(item):
    texto = f"{item.get('Benefícios','')} {item.get('Objetivo','')}"
    m_milhoes = re.search(r"R\$\s*(\d+(?:[.,]\d+)?)\s*milh[oõ]es", texto, re.I)
    if m_milhoes:
        return float(m_milhoes.group(1).replace(",", ".")) * 1_000_000
    m_mil = re.search(r"R\$\s*(\d+(?:[.,]\d+)?)\s*mil\b", texto, re.I)
    if m_mil:
        return float(m_mil.group(1).replace(",", ".")) * 1_000
    return None


def buscar_oportunidades_powerbi():
    headers = {"X-PowerBI-ResourceKey": RESOURCE_KEY, "Content-Type": "application/json"}
    selects = [
        {"Column": {"Expression": {"SourceRef": {"Source": "o"}}, "Property": c}, "Name": f"Oportunidades.{c}"}
        for c in COLUNAS
    ]
    payload = {
        "version": "1.0.0",
        "queries": [{
            "Query": {
                "Commands": [{
                    "SemanticQueryDataShapeCommand": {
                        "Query": {
                            "Version": 2,
                            "From": [{"Name": "o", "Entity": "Oportunidades", "Type": 0}],
                            "Select": selects,
                            "Where": [{
                                "Condition": {
                                    "In": {
                                        "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "o"}}, "Property": "Status"}}],
                                        "Values": [[{"Literal": {"Value": "'Ativo'"}}]],
                                    }
                                }
                            }],
                        },
                        "Binding": {
                            "Primary": {"Groupings": [{"Projections": list(range(len(COLUNAS)))}]},
                            "DataReduction": {"DataVolume": 4, "Primary": {"Window": {"Count": 500}}},
                            "Version": 1,
                        },
                        "ExecutionMetricsKind": 1,
                    }
                }]
            },
            "QueryId": "",
        }],
        "cancelQueries": [],
        "modelId": MODEL_ID,
    }

    resp_json = None
    for cluster in CLUSTERS:
        try:
            r = requests.post(
                f"https://{cluster}/public/reports/querydata?synchronous=true",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if r.ok:
                resp_json = r.json()
                break
        except Exception:
            continue

    if not resp_json:
        raise RuntimeError("Não foi possível consultar o cluster do Power BI do CRITT/UFJF.")

    ds = resp_json["results"][0]["result"]["data"]["dsr"]["DS"][0]
    vd = ds.get("ValueDicts", {})
    ph = ds["PH"][0]["DM0"]
    schema = ph[0].get("S", [])

    ultimo = [None] * len(schema)
    registros = []
    for row in ph:
        c_vals = row.get("C", [])
        r_mask = row.get("R", 0)
        n_mask = row.get("Ø", 0)
        atual = []
        idx_c = 0
        for i, s in enumerate(schema):
            if (n_mask >> i) & 1:
                val = None
            elif (r_mask >> i) & 1:
                val = ultimo[i]
            else:
                raw = c_vals[idx_c] if idx_c < len(c_vals) else None
                idx_c += 1
                dn = s.get("DN")
                if dn and isinstance(raw, int) and dn in vd and raw < len(vd[dn]):
                    val = vd[dn][raw]
                else:
                    val = raw
            ultimo[i] = val
            atual.append(val)
        registros.append(dict(zip(COLUNAS, atual)))
    return registros


def sincronizar():
    print("📡 Consultando API do Power BI do Radar de Oportunidades (CRITT/UFJF)...")
    registros = buscar_oportunidades_powerbi()
    print(f"📥 {len(registros)} oportunidades ativas recebidas do Power BI.")

    con = radar.conectar()
    con.executescript(SCHEMA_AUTO)
    colunas = {x[1] for x in con.execute("PRAGMA table_info(verificacoes_automaticas)")}
    for nome_col, tipo_col in (("sem_data_final", "INTEGER DEFAULT 0"), ("trecho_abertura", "TEXT")):
        if nome_col not in colunas:
            con.execute(f"ALTER TABLE verificacoes_automaticas ADD COLUMN {nome_col} {tipo_col}")

    ano_atual = datetime.now().year
    importados = 0
    ignorados_perfil = 0
    ignorados_vencidos = 0

    for item in registros:
        perfil = str(item.get("Perfil") or "").lower()
        if not any(k in perfil for k in ("startup", "mpe", "epp", "empresa")):
            ignorados_perfil += 1
            continue

        titulo = (item.get("Oportunidade") or "").strip()
        orgao = (item.get("Instituição") or "").strip()
        url = limpar_url(item.get("Acesso"))
        if not titulo or not orgao or not url.startswith("http"):
            continue

        # Ignora chamadas explicitamente de anos anteriores (ex: 2024 ou 2025) ou links de controle de 2025
        texto_ano = f"{titulo} {url}".lower()
        if any(str(a) in texto_ano for a in range(2020, ano_atual)) and "2027" not in texto_ano:
            ignorados_vencidos += 1
            continue

        prazo_iso, expirou = interpretar_data_critt(item.get("Prazo"), item.get("Fluxo Contínuo"))
        if expirou:
            ignorados_vencidos += 1
            continue

        objetivo = (item.get("Objetivo") or "").strip()
        beneficios = (item.get("Benefícios") or "").strip()
        requisitos = (item.get("Requisitos") or "").strip()
        perfil_txt = (item.get("Perfil") or "").strip()

        descricao = objetivo or beneficios or f"Oportunidade de {classificar_tipo(item).lower()} promovida por {orgao}."
        if len(descricao) > 260:
            descricao = descricao[:257].rstrip() + "..."

        req_final = requisitos or f"Elegibilidade: {perfil_txt}."
        if len(req_final) > 350:
            req_final = req_final[:347].rstrip() + "..."

        sem_data = prazo_iso is None
        trecho_abertura = (
            "Inscrições permanecem abertas em fluxo contínuo para submissão de propostas."
            if sem_data else f"Inscrições abertas até {prazo_iso}."
        )
        dados_edital = {
            "titulo": titulo,
            "orgao": orgao,
            "tipo": classificar_tipo(item),
            "estagio": "Qualquer",
            "descricao": descricao,
            "valor_maximo_reais": extrair_valor_reais(item),
            "prazo_inscricao": prazo_iso,
            "requisitos": req_final,
            "trecho_prazo": prazo_iso or "Fluxo contínuo",
        }

        radar.gravar(con, "CRITT / UFJF — Power BI Oficial", url, dados_edital, revisar=False)
        eid = radar.chave(orgao, titulo)
        edicao = normalizar(orgao) + "|" + normalizar(titulo)
        con.execute(
            "INSERT OR REPLACE INTO verificacoes_automaticas("
            "edital_id,url,versao,conferido_em,trecho_publico,trecho_prazo,trecho_responsavel,"
            "limite_iso,chave_edicao,sem_data_final,trecho_abertura) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                eid,
                url,
                VERSAO,
                agora().isoformat(),
                perfil_txt or "Startups e empresas inovadoras",
                dados_edital["trecho_prazo"],
                orgao,
                None,
                edicao,
                int(sem_data),
                trecho_abertura,
            ),
        )
        importados += 1

    con.commit()
    con.close()
    print(f"✅ Sincronização CRITT/UFJF concluída: {importados} oportunidades vigentes para startups/empresas gravadas (ignoradas: {ignorados_perfil} apenas acadêmicas, {ignorados_vencidos} vencidas/anos anteriores).")


if __name__ == "__main__":
    sincronizar()
