"""
Aba 4: Microdados e Tabela Analítica dos 295 Municípios de SC com Filtros Avançados.
"""

import pandas as pd
import streamlit as st
from streamlit_app.config import PORTE_OPCOES, PERFIL_SEVERIDADE_OPCOES, ZONA_PCI_OPCOES
from streamlit_app.utils.formatters import format_brazilian


def render_tab_dados(
    df_filtrado: pd.DataFrame,
    col_total: str,
    col_penal: str,
    label_escala: str,
    label_metrica_ativa: str,
    fator_pop: int,
    taxa_media_pop: float,
    grupo_key: str,
    year_param: str
) -> None:
    """Renderiza a tabela analítica municipal com filtros cruzados, ordenação e exportação de dados."""
    st.subheader("Base de Dados dos 295 Municípios de Santa Catarina")
    st.markdown("Explore, filtre e pesquise os indicadores detalhados dos municípios de Santa Catarina com múltiplos critérios simultâneos.")

    # Painel de Filtros Avançados em Grid
    col_s1, col_s2, col_s3, col_s4 = st.columns([4, 3, 3, 3])
    with col_s1:
        busca = st.text_input("🔍 Pesquisar município, região ou código IBGE:", placeholder="Ex.: Chapecó, 4205407, Joinville...")
    with col_s2:
        filtro_porte = st.selectbox("Porte Populacional (IBGE):", PORTE_OPCOES)
    with col_s3:
        filtro_severidade = st.selectbox("Perfil de Ocorrência:", PERFIL_SEVERIDADE_OPCOES)
    with col_s4:
        filtro_pci = st.selectbox("Acesso Forense (PCI):", ZONA_PCI_OPCOES)

    df_view = df_filtrado.copy()

    # Filtro de porte populacional
    if filtro_porte == "Pequeno Porte I (< 20 mil hab)":
        df_view = df_view[df_view["populacao_censo_2022"] < 20000]
    elif filtro_porte == "Pequeno Porte II (20 mil a 50 mil hab)":
        df_view = df_view[(df_view["populacao_censo_2022"] >= 20000) & (df_view["populacao_censo_2022"] <= 50000)]
    elif filtro_porte == "Médio Porte (50 mil a 100 mil hab)":
        df_view = df_view[(df_view["populacao_censo_2022"] > 50000) & (df_view["populacao_censo_2022"] <= 100000)]
    elif filtro_porte == "Grande Porte (> 100 mil hab)":
        df_view = df_view[df_view["populacao_censo_2022"] > 100000]

    # Filtro de severidade criminal
    if filtro_severidade == "Predomínio Penal (> 60% Crimes)":
        df_view = df_view[df_view["pct_penal_mun"] >= 60.0]
    elif filtro_severidade == "Predomínio Social (> 60% Rede SUAS)":
        df_view = df_view[df_view["pct_penal_mun"] < 40.0]
    elif filtro_severidade == "Picos Acima da Média Estadual":
        df_view = df_view[df_view["taxa_exibicao"] >= taxa_media_pop]

    # Filtro de distância pericial PCI
    if filtro_pci == "Vazios Críticos (> 50 km)":
        df_view = df_view[df_view["distancia_pci_km"] > 50.0]
    elif filtro_pci == "Atenção Moderada (25 a 50 km)":
        df_view = df_view[(df_view["distancia_pci_km"] >= 25.0) & (df_view["distancia_pci_km"] <= 50.0)]
    elif filtro_pci == "Resposta Imediata (< 25 km)":
        df_view = df_view[df_view["distancia_pci_km"] < 25.0]

    # Busca textual multidimensional
    if busca:
        b_norm = busca.strip().lower()
        df_view = df_view[
            df_view["municipio"].str.lower().str.contains(b_norm, na=False) |
            df_view["regiao_intermediaria"].str.lower().str.contains(b_norm, na=False) |
            df_view["regiao_imediata"].str.lower().str.contains(b_norm, na=False) |
            df_view["ibge_code"].astype(str).str.contains(b_norm, na=False)
        ]

    # Painel Resumo em 4 Métricas Dinâmicas
    tot_muns_view = len(df_view)
    pop_view = int(df_view["populacao_censo_2022"].sum())
    casos_view = int(df_view[col_total].sum())
    taxa_view = (casos_view / max(pop_view, 1)) * fator_pop

    rm1, rm2, rm3, rm4 = st.columns(4)
    with rm1:
        st.metric("Municípios Filtrados", f"{tot_muns_view} de {len(df_filtrado)}")
    with rm2:
        st.metric("População Coberta", format_brazilian(pop_view) + " hab")
    with rm3:
        st.metric("Volume de Denúncias", format_brazilian(casos_view))
    with rm4:
        st.metric("Taxa Média do Recorte", f"{taxa_view:.1f} / {fator_pop//1000}k hab")

    # Controles de Ordenação Flexível
    col_ord1, col_ord2 = st.columns([7, 3])
    with col_ord1:
        opcao_ordem = st.selectbox(
            "Ordenar Resultados por:",
            [
                f"Taxa Proporcional Ativa ({label_metrica_ativa})",
                "Total Geral de Ocorrências",
                "Indício Penal (Casos Criminais)",
                "Demanda Socioassistencial",
                "População Residente (Censo 2022)",
                "Distância até a Unidade PCI (km)",
                "Nome do Município (Alfabético)"
            ]
        )
    with col_ord2:
        direcao_ordem = st.radio("Direção da Ordenação:", ["Decrescente (Maior primeiro)", "Crescente (Menor primeiro)"], horizontal=True)

    col_sort_map = {
        f"Taxa Proporcional Ativa ({label_metrica_ativa})": "taxa_exibicao",
        "Total Geral de Ocorrências": col_total,
        "Indício Penal (Casos Criminais)": col_penal,
        "Demanda Socioassistencial": "demanda_social",
        "População Residente (Censo 2022)": "populacao_censo_2022",
        "Distância até a Unidade PCI (km)": "distancia_pci_km",
        "Nome do Município (Alfabético)": "municipio"
    }
    coluna_sort = col_sort_map[opcao_ordem]
    is_asc = (direcao_ordem == "Crescente (Menor primeiro)") if coluna_sort != "municipio" else (direcao_ordem == "Decrescente (Maior primeiro)")

    df_view_sorted = df_view.sort_values(by=coluna_sort, ascending=is_asc).reset_index(drop=True)
    df_view_sorted["ranking"] = [f"#{i+1}" for i in range(len(df_view_sorted))]

    colunas_exibicao = [
        "ranking",
        "municipio",
        "regiao_intermediaria",
        "populacao_censo_2022",
        col_total,
        col_penal,
        "demanda_social",
        "pct_penal_mun",
        "taxa_total_exibicao",
        "taxa_penal_exibicao",
        "distancia_pci_km",
        "pci_proxima"
    ]

    df_tabela_final = df_view_sorted[colunas_exibicao].rename(
        columns={
            "ranking": "Pos.",
            "municipio": "Município",
            "regiao_intermediaria": "Região Intermediária",
            "populacao_censo_2022": "População (2022)",
            col_total: "Total Ocorrências",
            col_penal: "Indício Penal",
            "demanda_social": "Demanda Social",
            "pct_penal_mun": "% Penal",
            "taxa_total_exibicao": f"Total ({label_escala})",
            "taxa_penal_exibicao": f"Penal ({label_escala})",
            "distancia_pci_km": "Dist. PCI (km)",
            "pci_proxima": "PCI de Referência"
        }
    )

    df_tabela_formatada = df_tabela_final.copy()
    df_tabela_formatada["População (2022)"] = df_tabela_formatada["População (2022)"].apply(format_brazilian)
    df_tabela_formatada["Total Ocorrências"] = df_tabela_formatada["Total Ocorrências"].apply(format_brazilian)
    df_tabela_formatada["Indício Penal"] = df_tabela_formatada["Indício Penal"].apply(format_brazilian)
    df_tabela_formatada["Demanda Social"] = df_tabela_formatada["Demanda Social"].apply(format_brazilian)
    df_tabela_formatada["% Penal"] = df_tabela_formatada["% Penal"].apply(lambda v: f"{v:.1f}%")
    df_tabela_formatada[f"Total ({label_escala})"] = df_tabela_formatada[f"Total ({label_escala})"].apply(lambda v: f"{v:.1f}")
    df_tabela_formatada[f"Penal ({label_escala})"] = df_tabela_formatada[f"Penal ({label_escala})"].apply(lambda v: f"{v:.1f}")
    df_tabela_formatada["Dist. PCI (km)"] = df_tabela_formatada["Dist. PCI (km)"].apply(lambda v: f"{v:.1f} km")

    st.dataframe(
        df_tabela_formatada,
        hide_index=True,
        use_container_width=True,
        width="stretch"
    )

    # Download em Múltiplos Formatos
    col_down1, col_down2 = st.columns(2)
    with col_down1:
        st.download_button(
            label="📥 Baixar Dados Filtrados em CSV",
            data=df_view_sorted.to_csv(index=False).encode("utf-8"),
            file_name=f"sc_disque100_municipios_{grupo_key}_{year_param}_{fator_pop}hab.csv",
            mime="text/csv"
        )
    with col_down2:
        st.download_button(
            label="📥 Baixar Dados Filtrados em JSON",
            data=df_view_sorted.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8"),
            file_name=f"sc_disque100_municipios_{grupo_key}_{year_param}_{fator_pop}hab.json",
            mime="application/json"
        )

