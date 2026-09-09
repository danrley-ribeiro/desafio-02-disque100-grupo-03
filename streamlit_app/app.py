#!/usr/bin/env python3
"""
=============================================================================
Dashboard de Inteligência Territorial do Disque 100 - Governo de Santa Catarina
=============================================================================
Aplicação Streamlit Modular e de Alta Performance.
Integração com DuckDB, Censo IBGE 2022, Polícia Científica (PCI-SC) e Folium.
=============================================================================
"""

import sys
from pathlib import Path

# Garante que a raiz do projeto e a pasta do app estejam no sys.path
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent if (APP_DIR.parent / "data").exists() else APP_DIR
for p in [str(PROJECT_ROOT), str(APP_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import streamlit as st

from streamlit_app.config import PAGE_CONFIG, CUSTOM_CSS
from streamlit_app.data_loader import carregar_dados, get_root_dir
from streamlit_app.utils.formatters import preparar_df_metricas
from streamlit_app.components.sidebar import render_sidebar
from streamlit_app.components.kpi_cards import render_kpi_cards
from streamlit_app.views.tab_mapa import render_tab_mapa
from streamlit_app.views.tab_grupos import render_tab_grupos
from streamlit_app.views.tab_pci import render_tab_pci
from streamlit_app.views.tab_dados import render_tab_dados
from streamlit_app.views.tab_metodologia import render_tab_metodologia


def main():
    """Função principal de orquestração da interface executiva."""
    st.set_page_config(**PAGE_CONFIG)
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    root_dir = get_root_dir()

    # HEADER GOVERNAMENTAL
    st.markdown('<div class="main-header">Governo do Estado de Santa Catarina</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Sistema Integrado de Inteligência Territorial do Disque 100 (2011–2026) | '
        'Perseguição Penal, Rede Assistencial e Capacidade Forense</div>',
        unsafe_allow_html=True
    )

    # Carregamento cacheado de alta performance dos dados
    df_kpi, df_pci, df_kpi_ano, audit_data, pci_dist_map = carregar_dados()

    # Barra lateral de filtros interativos
    (
        df_base_filtrado,
        label_periodo,
        year_param,
        metric_type_code,
        grupo_key,
        folium_topic,
        fator_pop,
        label_escala,
        regioes_escolhidas,
        region_code,
        camada_clusters,
        camada_pci,
        camada_rodovias
    ) = render_sidebar(df_kpi, df_kpi_ano)

    # Identificação das colunas do grupo selecionado
    if grupo_key == "geral":
        col_total = "total_denuncias"
        col_penal = "total_penal"
    else:
        col_total = f"{grupo_key}_total"
        col_penal = f"{grupo_key}_penal"

    # Preparação das métricas e enriquecimento vetorial
    df_filtrado, label_metrica_ativa = preparar_df_metricas(
        df_base_filtrado,
        col_total=col_total,
        col_penal=col_penal,
        fator_pop=fator_pop,
        metric_type_code=metric_type_code,
        pci_dist_map=pci_dist_map,
        label_escala=label_escala
    )

    # Agregações executivas para os cards
    total_casos = int(df_filtrado[col_total].sum())
    total_penal = int(df_filtrado[col_penal].sum())
    total_social = total_casos - total_penal
    pct_penal = (total_penal / max(total_casos, 1)) * 100
    pct_social = (total_social / max(total_casos, 1)) * 100
    pop_total = int(df_filtrado["populacao_censo_2022"].sum())
    taxa_media_pop = (total_casos / max(pop_total, 1)) * fator_pop
    taxa_media_penal = (total_penal / max(pop_total, 1)) * fator_pop

    # Renderização dos 4 Cards Executivos
    render_kpi_cards(
        total_casos=total_casos,
        total_penal=total_penal,
        total_social=total_social,
        pct_penal=pct_penal,
        pct_social=pct_social,
        taxa_media_pop=taxa_media_pop,
        taxa_media_penal=taxa_media_penal,
        label_periodo=label_periodo,
        label_escala=label_escala,
        fator_pop=fator_pop
    )

    # Abas estruturadas
    tab_mapa, tab_grupos, tab_pci, tab_dados, tab_metodologia = st.tabs([
        "Mapa Territorial e Picos",
        "Análise Estratégica por Grupos",
        "Capacidade Forense (PCI-SC)",
        "Microdados e Tabela Municipal",
        "Metodologia Jurídica e Fontes Oficiais"
    ])

    with tab_mapa:
        render_tab_mapa(
            df_filtrado=df_filtrado,
            label_metrica_ativa=label_metrica_ativa,
            fator_pop=fator_pop,
            folium_topic=folium_topic,
            metric_type_code=metric_type_code,
            region_code=region_code,
            year_param=year_param,
            camada_clusters=camada_clusters,
            camada_pci=camada_pci,
            camada_rodovias=camada_rodovias,
            root_dir=root_dir
        )

    with tab_grupos:
        render_tab_grupos(
            df_filtrado=df_filtrado,
            pop_total=pop_total,
            fator_pop=fator_pop,
            label_escala=label_escala,
            label_periodo=label_periodo,
            regioes_escolhidas=regioes_escolhidas
        )

    with tab_pci:
        render_tab_pci(
            df_filtrado=df_filtrado,
            df_pci=df_pci,
            col_penal=col_penal,
            label_escala=label_escala,
            label_periodo=label_periodo,
            fator_pop=fator_pop
        )

    with tab_dados:
        render_tab_dados(
            df_filtrado=df_filtrado,
            col_total=col_total,
            col_penal=col_penal,
            label_escala=label_escala,
            label_metrica_ativa=label_metrica_ativa,
            fator_pop=fator_pop,
            taxa_media_pop=taxa_media_pop,
            grupo_key=grupo_key,
            year_param=year_param
        )

    with tab_metodologia:
        render_tab_metodologia(
            audit_data=audit_data,
            root_dir=root_dir
        )


if __name__ == "__main__":
    main()

