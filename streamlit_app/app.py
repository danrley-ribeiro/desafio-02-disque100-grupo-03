#!/usr/bin/env python3
"""
=============================================================================
Painel do Disque 100 em Santa Catarina
=============================================================================
Triagem entre indicio de infracao penal e demanda socioassistencial nas
denuncias do Disque 100, cruzada com o Censo 2022 do IBGE e com a rede da
Policia Cientifica de Santa Catarina.

Execucao:
    streamlit run streamlit_app/app.py

Antes disso, a base precisa existir:
    python3 scripts/gerar_banco_duckdb_sc.py
    python3 scripts/build_annual_kpis.py
    python3 scripts/gerar_geo_pci_sc.py
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

# Apenas a raiz do projeto entra no sys.path. Acrescentar tambem a pasta do app
# permitia importar o mesmo modulo com e sem o prefixo do pacote, criando duas
# copias em memoria.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from streamlit_app.components.kpi_cards import render_kpi_cards
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.config import (
    CUSTOM_CSS,
    Filtros,
    NATUREZA_ROTULO,
    PAGE_CONFIG,
    SUBTITULO,
    TITULO,
    UNIDADE_DENUNCIAS,
    UNIDADE_ROTULO,
)
from streamlit_app.data_loader import carregar_base, carregar_mapa_folium, metadados_base
from streamlit_app.utils.formatters import preparar_metricas
from streamlit_app.views.tab_dados import render_tab_dados
from streamlit_app.views.tab_grupos import render_tab_grupos
from streamlit_app.views.tab_metodologia import render_tab_metodologia
from streamlit_app.views.tab_natureza_penal import render_tab_natureza_penal
from streamlit_app.views.tab_pci import render_tab_pci
from streamlit_app.views.tab_territorio import render_tab_territorio


def enriquecer(base: pd.DataFrame, distancia: pd.DataFrame, filtros: Filtros) -> pd.DataFrame:
    """
    Junta a matriz de distancia pericial e deriva as metricas do recorte.

    A juncao e vetorizada e municipios ausentes da matriz ficam com distancia
    indefinida. A versao anterior resolvia linha a linha com `map(lambda)` e
    atribuia 30 km e a faixa intermediaria a qualquer ausente.
    """
    if base.empty:
        return base

    colunas_distancia = [
        c for c in (
            "ibge_code", "distancia_pci_km", "pci_proxima", "pci_proxima_municipio",
            "faixa_distancia", "lat", "lng",
        )
        if c in distancia.columns
    ]
    if colunas_distancia and "ibge_code" in colunas_distancia:
        base = base.merge(
            distancia[colunas_distancia].astype({"ibge_code": str}),
            on="ibge_code",
            how="left",
        )

    coluna_total, coluna_penal = filtros.colunas()
    for coluna in (coluna_total, coluna_penal):
        if coluna not in base.columns:
            base[coluna] = 0

    return preparar_metricas(
        base,
        coluna_total=coluna_total,
        coluna_penal=coluna_penal,
        fator_pop=filtros.fator_pop,
        semestres=filtros.semestres_no_recorte,
        natureza=filtros.natureza,
    )


def resumir(df: pd.DataFrame, base_bruta: pd.DataFrame, filtros: Filtros) -> Dict[str, Any]:
    """Agregados do recorte, para os cartoes de resumo."""
    total = float(df["valor_total"].sum()) if not df.empty else 0.0
    penal = float(df["valor_penal"].sum()) if not df.empty else 0.0
    populacao = int(df["populacao_censo_2022"].sum()) if not df.empty else 0
    anos = max(filtros.semestres_no_recorte, 1) / 2.0

    # Quantos registros de violacao correspondem a essas denuncias, no recorte.
    fator = None
    if filtros.unidade_efetiva() == UNIDADE_DENUNCIAS and total:
        coluna = "registros_com_denuncia_identificavel"
        if coluna in base_bruta.columns:
            identificaveis = float(base_bruta[coluna].fillna(0).sum())
            fator = identificaveis / total if identificaveis else None
        elif "total_registros" in df.columns:
            fator = float(df["total_registros"].sum()) / total

    maioria_penal = None
    if filtros.unidade_efetiva() == UNIDADE_DENUNCIAS and "denuncias_unicas_maioria_penal" in base_bruta.columns:
        maioria_penal = float(base_bruta["denuncias_unicas_maioria_penal"].fillna(0).sum())

    return {
        "total": total,
        "penal": penal,
        "social": total - penal,
        "maioria_penal": maioria_penal,
        "pct_maioria_penal": (maioria_penal / total * 100.0) if (maioria_penal and total) else None,
        "pct_penal": (penal / total * 100.0) if total else None,
        "pct_social": ((total - penal) / total * 100.0) if total else None,
        "populacao": populacao,
        "taxa": (total / populacao / anos * filtros.fator_pop) if populacao else None,
        "taxa_penal": (penal / populacao / anos * filtros.fator_pop) if populacao else None,
        "semestres": filtros.semestres_no_recorte,
        "fator_expansao": fator,
    }


def main() -> None:
    st.set_page_config(**PAGE_CONFIG)
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    st.markdown(f'<div class="titulo-painel">{TITULO}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="subtitulo-painel">{SUBTITULO}</div>', unsafe_allow_html=True)

    dados = carregar_base()
    df_kpi = dados["kpis_grupos_municipios"]
    df_ano = dados["kpis_grupos_municipios_ano"]

    if df_kpi.empty:
        st.error(
            "Base analítica não encontrada. Execute, na raiz do projeto:\n\n"
            "```\npython3 scripts/gerar_banco_duckdb_sc.py\n"
            "python3 scripts/build_annual_kpis.py\n"
            "python3 scripts/gerar_geo_pci_sc.py\n```"
        )
        return

    metadados = metadados_base(dados["auditoria"])
    base, filtros = render_sidebar(df_kpi, df_ano, metadados)
    df = enriquecer(base, dados["distancia_pci"], filtros)

    # Faixa de contexto: diz em uma linha o que os numeros abaixo significam.
    st.markdown(
        '<div class="faixa-unidade">'
        f"Unidade: <b>{UNIDADE_ROTULO[filtros.unidade_efetiva()]}</b> &nbsp;·&nbsp; "
        f"Período: <b>{filtros.label_periodo}</b> &nbsp;·&nbsp; "
        f"Território: <b>{filtros.rotulo_territorio}</b> &nbsp;·&nbsp; "
        f"Grupo: <b>{filtros.rotulo_grupo}</b> &nbsp;·&nbsp; "
        f"Natureza: <b>{NATUREZA_ROTULO[filtros.natureza]}</b>"
        "</div>",
        unsafe_allow_html=True,
    )

    render_kpi_cards(resumir(df, base, filtros), filtros)

    abas = st.tabs([
        "Território",
        "Grupos vulneráveis",
        "Natureza penal",
        "Capacidade forense",
        "Tabela municipal",
        "Metodologia e auditoria",
    ])

    with abas[0]:
        render_tab_territorio(
            df,
            df_ano,
            filtros,
            dados["malha"],
            carregar_mapa_folium(),
            eixos=dados["eixos_rodoviarios"],
            df_pci=dados["dim_unidades_pci"],
        )
    with abas[1]:
        render_tab_grupos(df, filtros, metadados)
    with abas[2]:
        render_tab_natureza_penal(dados["kpis_categoria_penal"], filtros)
    with abas[3]:
        render_tab_pci(df, dados["dim_unidades_pci"], filtros, metadados)
    with abas[4]:
        render_tab_dados(df, filtros)
    with abas[5]:
        render_tab_metodologia(dados["auditoria"])


if __name__ == "__main__":
    main()
