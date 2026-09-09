"""
Componente do Painel Lateral (Sidebar) com Filtros Estratégicos e Metadados.
"""

from typing import Dict, Any, Tuple, List
import pandas as pd
import streamlit as st

from streamlit_app.config import (
    NATUREZA_OPCOES,
    GRUPO_OPCOES,
    FOLIUM_TOPIC_MAP,
    ESCALA_OPCOES
)


def render_sidebar(
    df_kpi: pd.DataFrame,
    df_kpi_ano: pd.DataFrame
) -> Tuple[pd.DataFrame, str, str, str, str, str, int, str, List[str], str, bool, bool, bool]:
    """
    Renderiza todos os filtros laterais e retorna os DataFrames e parâmetros selecionados.
    """
    st.sidebar.markdown("### Filtros Estratégicos")

    # 1. Filtro Temporal (Sliders e Radio)
    modo_temporal = st.sidebar.radio(
        "Período Temporal:",
        ["Acumulado Histórico (2011–2026)", "Ano Específico (Slider)", "Intervalo de Anos (Slider)"],
        index=0
    )

    if modo_temporal == "Ano Específico (Slider)":
        ano_selecionado = st.sidebar.select_slider(
            "Selecione o Ano:",
            options=list(range(2011, 2027)),
            value=2024
        )
        if not df_kpi_ano.empty:
            df_base = df_kpi_ano[df_kpi_ano["ano"] == ano_selecionado].copy()
        else:
            df_base = df_kpi.copy()
        label_periodo = f"Ano {ano_selecionado}"
        year_param = str(ano_selecionado)
    elif modo_temporal == "Intervalo de Anos (Slider)":
        anos_selecionados = st.sidebar.slider(
            "Intervalo de Anos:",
            min_value=2011,
            max_value=2026,
            value=(2019, 2024)
        )
        if not df_kpi_ano.empty:
            df_sub = df_kpi_ano[
                (df_kpi_ano["ano"] >= anos_selecionados[0]) & 
                (df_kpi_ano["ano"] <= anos_selecionados[1])
            ]
            num_cols = [
                c for c in df_sub.columns 
                if c not in ["ibge_code", "municipio", "regiao_intermediaria", "regiao_imediata", "populacao_censo_2022", "ano"]
            ]
            df_base = df_sub.groupby(
                ["ibge_code", "municipio", "regiao_intermediaria", "regiao_imediata", "populacao_censo_2022"],
                as_index=False
            )[num_cols].sum()
        else:
            df_base = df_kpi.copy()
        label_periodo = f"{anos_selecionados[0]} a {anos_selecionados[1]}"
        year_param = f"{anos_selecionados[0]}-{anos_selecionados[1]}"
    else:
        df_base = df_kpi.copy()
        label_periodo = "Acumulado (2011–2026)"
        year_param = "all"

    # 2. Natureza da Ocorrência (Radio Button)
    natureza_escolhida = st.sidebar.radio(
        "Natureza da Ocorrência:",
        list(NATUREZA_OPCOES.keys()),
        index=0
    )
    metric_type_code = NATUREZA_OPCOES[natureza_escolhida]

    # 3. Grupo Vulnerável (Selectbox)
    grupo_escolhido = st.sidebar.selectbox("Grupo Vulnerável:", list(GRUPO_OPCOES.keys()))
    grupo_key = GRUPO_OPCOES[grupo_escolhido]
    folium_topic = FOLIUM_TOPIC_MAP.get(grupo_key, "total")

    # 4. Proporção Populacional (Radio Button)
    escala_escolhida = st.sidebar.radio(
        "Proporção Populacional:",
        list(ESCALA_OPCOES.keys()),
        index=0
    )
    fator_pop = ESCALA_OPCOES[escala_escolhida]
    label_escala = f"Taxa / {fator_pop // 1000}k Hab"

    # 5. Regiões Geográficas Intermediárias (Multiselect)
    regioes_disponiveis = sorted(list(df_kpi["regiao_intermediaria"].dropna().unique()))
    regioes_escolhidas = st.sidebar.multiselect(
        "Regiões Geográficas (Vazio = Todas as 7):",
        options=regioes_disponiveis,
        default=[]
    )

    if regioes_escolhidas:
        df_filtrado = df_base[df_base["regiao_intermediaria"].isin(regioes_escolhidas)].copy()
        region_code = regioes_escolhidas[0] if len(regioes_escolhidas) == 1 else "all"
    else:
        df_filtrado = df_base.copy()
        region_code = "all"

    # 6. Camadas e Clusters do Mapa (Checkboxes)
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### Camadas do Mapa")
    camada_clusters = st.sidebar.checkbox("Exibir Clusters de Concentração", value=True)
    camada_pci = st.sidebar.checkbox("Exibir Unidades Forenses (PCI-SC)", value=True)
    camada_rodovias = st.sidebar.checkbox("Exibir Rodovias Principais", value=True)

    # Metadados no Sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("""
    **Metadados da Base Oficial:**
    - Registros Analisados: 696.535 em SC
    - População Base: 7.610.361 hab (Censo IBGE 2022)
    - Unidades Forenses: 30 unidades PCI-SC
    - Motor de Processamento: DuckDB Colunar
    - Integridade: Hashes SHA-256 Auditados
    """)

    return (
        df_filtrado,
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
    )

