"""
=============================================================================
Carregamento e cache dos dados do painel
=============================================================================
Le a base analitica do DuckDB, com queda para Parquet, e normaliza os nomes de
coluna que variam entre a tabela acumulada e a tabela por ano e semestre, para
que as abas nao precisem saber de qual fonte o recorte veio.

Tudo o que e lido de disco passa por `st.cache_data`. Antes, o HTML do mapa
Folium, de 1,1 MB, era relido a cada interacao da barra lateral.
=============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

try:
    import duckdb
except ImportError:  # o painel opera sem DuckDB, lendo os Parquet
    duckdb = None

TABELAS = (
    "kpis_grupos_municipios",
    "kpis_grupos_municipios_ano",
    "kpis_categoria_penal",
    "dim_unidades_pci",
)

# Colunas cujos nomes divergem entre as tabelas materializadas.
ALIASES_COLUNA: Dict[str, Tuple[str, ...]] = {
    "total_registros": ("total_registros", "total_denuncias"),
    "municipio": ("municipio", "municipio_nome"),
}


def get_root_dir() -> Path:
    """Raiz do projeto, a partir da localizacao deste modulo."""
    atual = Path(__file__).resolve().parent
    for candidato in (atual.parent, atual, atual.parent.parent):
        if (candidato / "data").exists():
            return candidato
    return atual.parent


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Garante os nomes canonicos de coluna esperados pelas abas."""
    if df.empty:
        return df
    for canonico, variantes in ALIASES_COLUNA.items():
        if canonico in df.columns:
            continue
        for v in variantes:
            if v in df.columns:
                df[canonico] = df[v]
                break
    return df


@st.cache_data(ttl=3600, show_spinner="Carregando base analítica...")
def carregar_base() -> Dict[str, Any]:
    """
    Carrega as tabelas analiticas, a auditoria, a matriz de distancia pericial
    e a malha municipal. Devolve um dicionario para que acrescentar uma fonte
    nao altere a assinatura de quem consome.
    """
    root = get_root_dir()
    proc = root / "data" / "processed"
    tabelas: Dict[str, pd.DataFrame] = {t: pd.DataFrame() for t in TABELAS}

    duck = next(
        (p for p in (
            root / "data" / "database" / "sc_disque100_analitico.duckdb",
            root / "sc_disque100_analitico.duckdb",
        ) if p.exists()),
        None,
    )

    if duck and duckdb:
        try:
            con = duckdb.connect(str(duck), read_only=True)
            existentes = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
            for t in TABELAS:
                if t in existentes:
                    tabelas[t] = con.execute(f'SELECT * FROM "{t}"').fetchdf()
            con.close()
        except Exception as err:
            st.warning(
                f"Não foi possível consultar o DuckDB ({err}). Usando os arquivos Parquet."
            )

    # Queda para Parquet, tabela por tabela.
    parquet_por_tabela = {
        "kpis_grupos_municipios": "sc_kpis_grupos_municipios.parquet",
        "kpis_grupos_municipios_ano": "sc_kpis_grupos_municipios_ano.parquet",
        "kpis_categoria_penal": "sc_kpis_categoria_penal.parquet",
        "dim_unidades_pci": "sc_dim_pci.parquet",
    }
    for tabela, arquivo in parquet_por_tabela.items():
        if tabelas[tabela].empty:
            caminho = proc / arquivo
            if caminho.exists():
                tabelas[tabela] = pd.read_parquet(caminho)

    for t in TABELAS:
        tabelas[t] = _normalizar(tabelas[t])

    return {
        **tabelas,
        "auditoria": _ler_json(proc / "sc_relatorio_auditoria_dados.json") or {},
        "distancia_pci": _ler_distancia_pci(proc / "sc_municipios_distancia_pci.json"),
        "malha": _ler_json(proc / "sc_malha_municipios.geojson"),
        "eixos_rodoviarios": _ler_eixos(proc / "sc_eixos_rodoviarios.json"),
    }


def _ler_json(caminho: Path) -> Optional[Any]:
    if not caminho.exists():
        return None
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _ler_eixos(caminho: Path) -> List[Dict[str, Any]]:
    """
    Eixos rodoviarios de referencia para a camada de contexto do mapa.

    Se o arquivo nao existir, cai para a definicao em `scripts/`, de modo que a
    camada nunca desapareca silenciosamente.
    """
    bruto = _ler_json(caminho)
    if isinstance(bruto, dict) and bruto.get("eixos"):
        return bruto["eixos"]
    try:
        import sys

        scripts = str(get_root_dir() / "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        from eixos_rodoviarios_sc import EIXOS_RODOVIARIOS

        return list(EIXOS_RODOVIARIOS)
    except Exception:
        return []


def _ler_distancia_pci(caminho: Path) -> pd.DataFrame:
    """
    Matriz de distancia pericial como DataFrame, para juncao vetorizada.

    A versao anterior resolvia municipio por municipio com tres `map(lambda)`
    e atribuia valores inventados aos ausentes.
    """
    bruto = _ler_json(caminho)
    if not bruto:
        return pd.DataFrame(
            columns=["ibge_code", "distancia_pci_km", "pci_proxima", "faixa_distancia"]
        )

    # Formato atual: {"metadata": {...}, "municipios": {...}}.
    registros = bruto.get("municipios", bruto) if isinstance(bruto, dict) else {}
    linhas: List[Dict[str, Any]] = []
    for cid, v in registros.items():
        if not isinstance(v, dict):
            continue
        linhas.append({
            "ibge_code": str(cid),
            "distancia_pci_km": v.get("distancia_pci_km_linha_reta", v.get("distancia_pci_km")),
            "pci_proxima": v.get("pci_proxima"),
            "pci_proxima_municipio": v.get("pci_proxima_municipio"),
            "faixa_distancia": v.get("faixa_distancia", v.get("zona_resposta")),
            "lat": v.get("lat"),
            "lng": v.get("lng"),
        })
    return pd.DataFrame(linhas)


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_mapa_folium() -> Optional[str]:
    """
    HTML do mapa Folium pre-gerado, lido uma unica vez por sessao.

    Devolve None quando o arquivo nao existe, e a aba mostra a instrucao de
    como gera-lo em vez de falhar.
    """
    root = get_root_dir()
    for caminho in (
        root / "dashboards" / "dashboard_sc_disque100_folium.html",
        root / "dashboard_sc_disque100_folium.html",
    ):
        if caminho.exists():
            return caminho.read_text(encoding="utf-8")
    return None


def metadados_base(auditoria: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai da auditoria os numeros exibidos como metadados.

    Sao lidos do relatorio, nunca escritos a mao no texto do painel: a barra
    lateral antiga trazia "696.535" fixo em uma string de markdown.
    """
    totais = auditoria.get("totais", {}) or {}
    demografia = auditoria.get("demografia", {}) or {}
    pci = auditoria.get("policia_cientifica", {}) or {}
    conciliacao = auditoria.get("conciliacao_municipal", {}) or {}
    return {
        "periodo": totais.get("periodo"),
        "registros": totais.get("registros_de_violacao"),
        "registros_municipalizados": conciliacao.get("registros_atribuidos_a_municipio"),
        "denuncias_unicas": totais.get("denuncias_unicas_identificaveis"),
        "populacao": demografia.get("populacao_total"),
        "municipios": demografia.get("municipios"),
        "unidades_pci": pci.get("total_unidades"),
        "composicao_pci": pci.get("composicao", {}),
        "atualizado_em": auditoria.get("timestamp_auditoria"),
        "anos_incompletos": auditoria.get("anos_incompletos", {}) or {},
        "comparabilidade": auditoria.get("comparabilidade_grupos", {}) or {},
    }
