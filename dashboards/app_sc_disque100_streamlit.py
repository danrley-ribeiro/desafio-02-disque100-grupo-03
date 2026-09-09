#!/usr/bin/env python3
"""
=============================================================================
Dashboard de Inteligência Territorial do Disque 100 - Governo de Santa Catarina
=============================================================================
Painel Executivo em Streamlit integrado a DuckDB, Censo IBGE 2022 e Folium.
Classificação por Grupos Vulneráveis, Triagem Penal vs Assistencial e Taxas
proporcionais customizáveis por 10k, 50k e 100k habitantes.
=============================================================================
"""

import os
import json
from pathlib import Path
import pandas as pd

try:
    import streamlit as st
    import streamlit.components.v1 as components
except ImportError:
    st = None
    components = None

try:
    import duckdb
except ImportError:
    duckdb = None


CURRENT_FILE_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_FILE_DIR.parent if CURRENT_FILE_DIR.name == "dashboards" else CURRENT_FILE_DIR


def carregar_dados():
    """Carrega dados da base única oficial DuckDB com fallback para CSV (suporta pastas organizadas)."""
    duck_candidates = [
        ROOT_DIR / "data" / "database" / "sc_disque100_analitico.duckdb",
        ROOT_DIR / "sc_disque100_analitico.duckdb"
    ]
    duck_path = next((p for p in duck_candidates if p.exists()), None)

    if duck_path and duckdb:
        con = duckdb.connect(str(duck_path), read_only=True)
        df_kpi = con.execute("SELECT * FROM kpis_grupos_municipios").fetchdf()
        df_pci = con.execute("SELECT * FROM dim_unidades_pci").fetchdf()
        try:
            df_kpi_ano = con.execute("SELECT * FROM kpis_grupos_municipios_ano").fetchdf()
        except Exception:
            df_kpi_ano = pd.DataFrame()
        con.close()
    else:
        kpi_candidates = [
            ROOT_DIR / "data" / "processed" / "sc_kpis_grupos_municipios.csv",
            ROOT_DIR / "sc_kpis_grupos_municipios.csv"
        ]
        pci_candidates = [
            ROOT_DIR / "data" / "processed" / "sc_dim_pci.parquet",
            ROOT_DIR / "sc_dim_pci.parquet"
        ]
        ano_candidates = [
            ROOT_DIR / "data" / "processed" / "sc_kpis_grupos_municipios_ano.parquet",
            ROOT_DIR / "sc_kpis_grupos_municipios_ano.parquet"
        ]
        kpi_file = next((p for p in kpi_candidates if p.exists()), None)
        pci_file = next((p for p in pci_candidates if p.exists()), None)
        ano_file = next((p for p in ano_candidates if p.exists()), None)
        df_kpi = pd.read_csv(kpi_file)
        df_pci = pd.read_parquet(pci_file) if pci_file and pci_file.exists() else pd.DataFrame()
        df_kpi_ano = pd.read_parquet(ano_file) if ano_file and ano_file.exists() else pd.DataFrame()

    if df_kpi_ano.empty:
        ano_candidates = [
            ROOT_DIR / "data" / "processed" / "sc_kpis_grupos_municipios_ano.parquet",
            ROOT_DIR / "sc_kpis_grupos_municipios_ano.parquet"
        ]
        ano_file = next((p for p in ano_candidates if p.exists()), None)
        if ano_file and ano_file.exists():
            df_kpi_ano = pd.read_parquet(ano_file)

    audit_candidates = [
        ROOT_DIR / "data" / "processed" / "sc_relatorio_auditoria_dados.json",
        ROOT_DIR / "sc_relatorio_auditoria_dados.json"
    ]
    audit_file = next((p for p in audit_candidates if p.exists()), None)
    audit_data = {}
    if audit_file and audit_file.exists():
        with open(audit_file, "r", encoding="utf-8") as f:
            audit_data = json.load(f)

    # Distâncias oficiais e unidades forenses da PCI-SC por município
    pci_dist_candidates = [
        ROOT_DIR / "data" / "processed" / "sc_municipios_distancia_pci.json",
        ROOT_DIR / "sc_municipios_distancia_pci.json"
    ]
    pci_dist_file = next((p for p in pci_dist_candidates if p.exists()), None)
    pci_dist_map = {}
    if pci_dist_file and pci_dist_file.exists():
        with open(pci_dist_file, "r", encoding="utf-8") as f:
            pci_dist_map = json.load(f)

    return df_kpi, df_pci, df_kpi_ano, audit_data, pci_dist_map


def run_streamlit_app():
    if st is None:
        print("[-] Streamlit não está instalado no ambiente atual. Instale com: pip install streamlit")
        return

    st.set_page_config(
        page_title="Inteligência Disque 100 - Governo de Santa Catarina",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Estilos customizados institucionais (sóbrios, padrão governamental)
    st.markdown("""
        <style>
        .main-header {
            font-size: 1.7rem;
            font-weight: 800;
            color: #0f172a;
            margin-bottom: 0.1rem;
            letter-spacing: -0.5px;
        }
        .sub-header {
            font-size: 0.95rem;
            color: #475569;
            margin-bottom: 1.2rem;
            font-weight: 500;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 44px;
            white-space: pre-wrap;
            border-radius: 6px 6px 0px 0px;
            font-weight: 600;
            font-size: 13.5px;
            padding: 0 16px;
        }
        .metric-container {
            border-left: 4px solid #3b82f6;
            padding: 10px 14px;
            background: #f8fafc;
            border-radius: 4px;
        }
        </style>
    """, unsafe_allow_html=True)

    df_kpi, df_pci, df_kpi_ano, audit_data, pci_dist_map = carregar_dados()

    # HEADER GOVERNAMENTAL
    st.markdown('<div class="main-header">Governo do Estado de Santa Catarina</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Sistema Integrado de Inteligência Territorial do Disque 100 (2011–2026) | Perseguição Penal, Rede Assistencial e Capacidade Forense</div>', unsafe_allow_html=True)

    # =========================================================================
    # SIDEBAR: FILTROS ESTRATÉGICOS (TEMPORAL, GRUPOS, RADIO, MULTISELECT)
    # =========================================================================
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
            df_sub = df_kpi_ano[(df_kpi_ano["ano"] >= anos_selecionados[0]) & (df_kpi_ano["ano"] <= anos_selecionados[1])]
            num_cols = [c for c in df_sub.columns if c not in ["ibge_code", "municipio", "regiao_intermediaria", "regiao_imediata", "populacao_censo_2022", "ano"]]
            df_base = df_sub.groupby(["ibge_code", "municipio", "regiao_intermediaria", "regiao_imediata", "populacao_censo_2022"], as_index=False)[num_cols].sum()
        else:
            df_base = df_kpi.copy()
        label_periodo = f"{anos_selecionados[0]} a {anos_selecionados[1]}"
        year_param = f"{anos_selecionados[0]}-{anos_selecionados[1]}"
    else:
        df_base = df_kpi.copy()
        label_periodo = "Acumulado (2011–2026)"
        year_param = "all"

    # 2. Natureza da Ocorrência (Radio Button)
    natureza_opcoes = {
        "Total Geral (Consolidado)": "total",
        "Indício Penal (Crimes e Perícia Forense)": "penal",
        "Demanda Socioassistencial (Rede SUAS)": "social"
    }
    natureza_escolhida = st.sidebar.radio(
        "Natureza da Ocorrência:",
        list(natureza_opcoes.keys()),
        index=0
    )
    metric_type_code = natureza_opcoes[natureza_escolhida]

    # 3. Grupo Vulnerável (Selectbox)
    grupo_opcoes = {
        "Todos os Grupos (Visão Geral)": "geral",
        "Crianças e Adolescentes (ECA)": "criancas",
        "Mulheres (Violência de Gênero / Doméstica)": "mulheres",
        "Pessoas Idosas (Estatuto da Pessoa Idosa)": "idosos",
        "Pessoas com Deficiência (Estatuto PCD)": "pcd",
        "População LGBTQIA+": "lgbt",
        "Sistema Prisional e Situação de Rua": "prisional"
    }
    grupo_escolhido = st.sidebar.selectbox("Grupo Vulnerável:", list(grupo_opcoes.keys()))
    grupo_key = grupo_opcoes[grupo_escolhido]

    folium_topic_map = {
        "geral": "total",
        "criancas": "crianca",
        "mulheres": "mulher",
        "idosos": "idoso",
        "pcd": "pcd",
        "lgbt": "lgbt",
        "prisional": "preso"
    }
    folium_topic = folium_topic_map.get(grupo_key, "total")

    # 4. Proporção Populacional (Radio Button)
    escala_opcoes = {
        "Taxa por 10.000 Habitantes (Padrão Estadual / Picos)": 10000,
        "Taxa por 50.000 Habitantes (Porte Médio Regional)": 50000,
        "Taxa por 100.000 Habitantes (Padrão SENASP / Atlas)": 100000
    }
    escala_escolhida = st.sidebar.radio(
        "Proporção Populacional:",
        list(escala_opcoes.keys()),
        index=0
    )
    fator_pop = escala_opcoes[escala_escolhida]
    label_escala = f"Taxa / {fator_pop // 1000}k Hab"

    # 5. Regiões Geográficas Intermediárias (Multiselect)
    regioes_disponiveis = sorted(list(df_kpi["regiao_intermediaria"].unique()))
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

    # =========================================================================
    # CÁLCULO DAS MÉTRICAS NA BASE SELECIONADA
    # =========================================================================
    if grupo_key == "geral":
        col_total = "total_denuncias"
        col_penal = "total_penal"
    else:
        col_total = f"{grupo_key}_total"
        col_penal = f"{grupo_key}_penal"

    # Criação das taxas com base no fator populacional escolhido (10k, 50k, 100k)
    # Enriquecimento com distâncias da PCI-SC e taxas analíticas
    df_filtrado["distancia_pci_km"] = df_filtrado["ibge_code"].astype(str).map(lambda c: pci_dist_map.get(c, {}).get("distancia_pci_km", 30.0))
    df_filtrado["pci_proxima"] = df_filtrado["ibge_code"].astype(str).map(lambda c: pci_dist_map.get(c, {}).get("pci_proxima", "PCI Regional"))
    df_filtrado["zona_resposta"] = df_filtrado["ibge_code"].astype(str).map(lambda c: pci_dist_map.get(c, {}).get("zona_resposta", "Atenção (25 a 50 km)"))

    df_filtrado["taxa_exibicao"] = (df_filtrado[col_total] / df_filtrado["populacao_censo_2022"]) * fator_pop
    df_filtrado["taxa_total_exibicao"] = (df_filtrado[col_total] / df_filtrado["populacao_censo_2022"]) * fator_pop
    df_filtrado["taxa_penal_exibicao"] = (df_filtrado[col_penal] / df_filtrado["populacao_censo_2022"]) * fator_pop
    df_filtrado["demanda_social"] = df_filtrado[col_total] - df_filtrado[col_penal]
    df_filtrado["taxa_social_exibicao"] = (df_filtrado["demanda_social"] / df_filtrado["populacao_censo_2022"]) * fator_pop
    df_filtrado["pct_penal_mun"] = (df_filtrado[col_penal] / df_filtrado[col_total].apply(lambda x: max(x, 1))) * 100

    # Métrica ativa para ranking e gráficos de acordo com a Natureza da Ocorrência
    if metric_type_code == "penal":
        df_filtrado["taxa_exibicao"] = df_filtrado["taxa_penal_exibicao"]
        label_metrica_ativa = f"Indício Penal ({label_escala})"
    elif metric_type_code == "social":
        df_filtrado["taxa_exibicao"] = df_filtrado["taxa_social_exibicao"]
        label_metrica_ativa = f"Demanda Socioassistencial ({label_escala})"
    else:
        df_filtrado["taxa_exibicao"] = df_filtrado["taxa_total_exibicao"]
        label_metrica_ativa = f"Total de Ocorrências ({label_escala})"

    total_casos = int(df_filtrado[col_total].sum())
    total_penal = int(df_filtrado[col_penal].sum())
    total_social = total_casos - total_penal
    pct_penal = (total_penal / max(total_casos, 1)) * 100
    pct_social = (total_social / max(total_casos, 1)) * 100
    pop_total = int(df_filtrado["populacao_censo_2022"].sum())
    taxa_media_pop = (total_casos / max(pop_total, 1)) * fator_pop
    taxa_media_penal = (total_penal / max(pop_total, 1)) * fator_pop

    # Textos de ajuda institucionais aprofundados
    help_penal = (
        "Indício de Infração Penal: Ocorrências relatadas que configuram tipicidade "
        "prevista no Código Penal (arts. 121, 129, 136, 213, 217-A), no ECA (Lei 8.069/90), "
        "na Lei Henry Borel (Lei 14.344/22) ou no Estatuto da Pessoa Idosa (Lei 10.741/03). "
        "Exigem apuração imediata por órgãos de persecução policial (Polícia Civil de SC) "
        "e realização de exames de corpo de delito e coleta de vestígios pela Polícia Científica (PCI-SC)."
    )

    help_social = (
        "Demanda Socioassistencial: Ocorrências caracterizadas por vulnerabilidades sociais, "
        "conflitos familiares, negligência socioeconômica ou evasão escolar, sem presença de dolo "
        "ou tipicidade penal imediata. São de competência da rede SUAS (CRAS e CREAS), "
        "Conselhos Tutelares e Defensoria Pública, não demandando inquérito policial ou perícia forense."
    )

    # 4 Cards Executivos
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(
            label=f"Total de Ocorrências ({label_periodo})",
            value=f"{total_casos:,}".replace(",", "."),
            help="Total acumulado de denúncias no grupo e território selecionados."
        )
    with kpi2:
        st.metric(
            label="Indício Penal (Crimes)",
            value=f"{total_penal:,}".replace(",", "."),
            delta=f"{pct_penal:.1f}% do volume",
            help=help_penal
        )
    with kpi3:
        st.metric(
            label="Demanda Socioassistencial",
            value=f"{total_social:,}".replace(",", "."),
            delta=f"{pct_social:.1f}% do volume",
            delta_color="off",
            help=help_social
        )
    with kpi4:
        st.metric(
            label=f"Média {label_escala}",
            value=f"{taxa_media_pop:.1f}",
            delta=f"Penal: {taxa_media_penal:.1f}",
            delta_color="off",
            help=f"Taxa proporcional calculada com base na população oficial do Censo IBGE 2022 para {fator_pop:,} habitantes."
        )

    st.markdown("---")

    # =========================================================================
    # ABAS DE ANÁLISE AMPLIADAS E ESTRUTURADAS
    # =========================================================================
    tab_mapa, tab_grupos, tab_pci, tab_dados, tab_metodologia = st.tabs([
        "Mapa Territorial e Picos",
        "Análise Estratégica por Grupos",
        "Capacidade Forense (PCI-SC)",
        "Microdados e Tabela Municipal",
        "Metodologia Jurídica e Fontes Oficiais"
    ])

    # -------------------------------------------------------------------------
    # ABA 1: MAPA NATIVO + GRÁFICO DOS 10 MAIORES FOCOS
    # -------------------------------------------------------------------------
    with tab_mapa:
        st.subheader("Visualização Cartográfica e Focos Espaciais")
        st.caption(f"Malhas vetoriais oficiais dos 295 municípios, rodovias de ligação, 30 unidades da PCI-SC e os 10 maiores picos proporcionais na base de {fator_pop:,} habitantes ({label_metrica_ativa}).")

        map_candidates = [
            ROOT_DIR / "dashboards" / "dashboard_sc_disque100_folium.html",
            ROOT_DIR / "dashboard_sc_disque100_folium.html"
        ]
        html_map_path = next((p for p in map_candidates if p.exists()), None)
        if html_map_path and html_map_path.exists():
            with open(html_map_path, "r", encoding="utf-8") as f:
                raw_folium_html = f.read()

            # Injeção dinâmica do estado dos filtros do Streamlit diretamente no DOM do Leaflet
            config_injection = f"""
            <script>
                window.ACTIVE_STREAMLIT_CONFIG = {{
                    topic: "{folium_topic}",
                    metricType: "{metric_type_code}",
                    scale: {fator_pop},
                    region: "{region_code}",
                    year: "{year_param}",
                    showClusters: {str(camada_clusters).lower()},
                    showPCI: {str(camada_pci).lower()},
                    showRoads: {str(camada_rodovias).lower()}
                }};
                (function applyNow() {{
                    if (typeof window.applyActiveFilters === 'function') {{
                        window.applyActiveFilters(window.ACTIVE_STREAMLIT_CONFIG);
                    }} else {{
                        setTimeout(applyNow, 50);
                    }}
                }})();
            </script>
            """

            folium_html = raw_folium_html.replace("<head>", f"<head>\n{config_injection}\n")
            if "</body>" in folium_html:
                folium_html = folium_html.replace("</body>", f"{config_injection}\n</body>")

            components.html(folium_html, height=720, scrolling=False)
        else:
            st.warning("Arquivo do mapa georreferenciado não encontrado. Execute `python3 generate_sc_disque100_folium_dashboard.py`.")

        st.markdown(f"### Top 10 Municípios com Maior Concentração Proporcional - {label_metrica_ativa}")
        df_top10 = df_filtrado.sort_values(by="taxa_exibicao", ascending=False).head(10)
        st.bar_chart(
            data=df_top10.set_index("municipio")["taxa_exibicao"],
            color="#3b82f6"
        )

    # -------------------------------------------------------------------------
    # ABA 2: ANÁLISE ESTRATÉGICA POR GRUPOS VULNERÁVEIS
    # -------------------------------------------------------------------------
    with tab_grupos:
        st.subheader("Distribuição Comparativa dos Grupos Vulneráveis em Santa Catarina")
        st.markdown("""
        Esta seção compara o perfil de incidência entre os 6 grupos prioritários catalogados,
        demonstrando a disparidade de gravidade penal entre as tipologias de atendimento.
        """)

        # Agregação geral dos grupos no filtro territorial ativo
        grupos_dados = [
            {
                "Grupo Vulnerável": "Crianças e Adolescentes (ECA)",
                "Total Ocorrências": int(df_filtrado["criancas_total"].sum()),
                "Indício Penal": int(df_filtrado["criancas_penal"].sum()),
                "Demanda Social": int(df_filtrado["criancas_total"].sum() - df_filtrado["criancas_penal"].sum()),
                "Percentual Penal (%)": round((df_filtrado["criancas_penal"].sum() / max(df_filtrado["criancas_total"].sum(), 1)) * 100, 1),
                f"{label_escala}": round((df_filtrado["criancas_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
            },
            {
                "Grupo Vulnerável": "Pessoas Idosas",
                "Total Ocorrências": int(df_filtrado["idosos_total"].sum()),
                "Indício Penal": int(df_filtrado["idosos_penal"].sum()),
                "Demanda Social": int(df_filtrado["idosos_total"].sum() - df_filtrado["idosos_penal"].sum()),
                "Percentual Penal (%)": round((df_filtrado["idosos_penal"].sum() / max(df_filtrado["idosos_total"].sum(), 1)) * 100, 1),
                f"{label_escala}": round((df_filtrado["idosos_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
            },
            {
                "Grupo Vulnerável": "Pessoas com Deficiência (PCD)",
                "Total Ocorrências": int(df_filtrado["pcd_total"].sum()),
                "Indício Penal": int(df_filtrado["pcd_penal"].sum()),
                "Demanda Social": int(df_filtrado["pcd_total"].sum() - df_filtrado["pcd_penal"].sum()),
                "Percentual Penal (%)": round((df_filtrado["pcd_penal"].sum() / max(df_filtrado["pcd_total"].sum(), 1)) * 100, 1),
                f"{label_escala}": round((df_filtrado["pcd_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
            },
            {
                "Grupo Vulnerável": "Mulheres (Violência Doméstica / Gênero)",
                "Total Ocorrências": int(df_filtrado["mulheres_total"].sum()),
                "Indício Penal": int(df_filtrado["mulheres_penal"].sum()),
                "Demanda Social": int(df_filtrado["mulheres_total"].sum() - df_filtrado["mulheres_penal"].sum()),
                "Percentual Penal (%)": round((df_filtrado["mulheres_penal"].sum() / max(df_filtrado["mulheres_total"].sum(), 1)) * 100, 1),
                f"{label_escala}": round((df_filtrado["mulheres_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
            },
            {
                "Grupo Vulnerável": "Sistema Prisional e Situação de Rua",
                "Total Ocorrências": int(df_filtrado["prisional_total"].sum()),
                "Indício Penal": int(df_filtrado["prisional_penal"].sum()),
                "Demanda Social": int(df_filtrado["prisional_total"].sum() - df_filtrado["prisional_penal"].sum()),
                "Percentual Penal (%)": round((df_filtrado["prisional_penal"].sum() / max(df_filtrado["prisional_total"].sum(), 1)) * 100, 1),
                f"{label_escala}": round((df_filtrado["prisional_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
            },
            {
                "Grupo Vulnerável": "População LGBTQIA+",
                "Total Ocorrências": int(df_filtrado["lgbt_total"].sum()),
                "Indício Penal": int(df_filtrado["lgbt_penal"].sum()),
                "Demanda Social": int(df_filtrado["lgbt_total"].sum() - df_filtrado["lgbt_penal"].sum()),
                "Percentual Penal (%)": round((df_filtrado["lgbt_penal"].sum() / max(df_filtrado["lgbt_total"].sum(), 1)) * 100, 1),
                f"{label_escala}": round((df_filtrado["lgbt_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
            }
        ]
        df_grupos_comp = pd.DataFrame(grupos_dados)

        col_g1, col_g2 = st.columns([5, 5])
        with col_g1:
            st.markdown("#### Volume Total por Grupo Vulnerável")
            st.bar_chart(
                data=df_grupos_comp.set_index("Grupo Vulnerável")["Total Ocorrências"],
                color="#2563eb"
            )
        with col_g2:
            st.markdown("#### Taxa de Severidade Penal (% de Casos Criminais)")
            st.bar_chart(
                data=df_grupos_comp.set_index("Grupo Vulnerável")["Percentual Penal (%)"],
                color="#dc2626"
            )

        st.markdown("#### Matriz Sintética de Atendimento por Grupo Vulnerável")
        st.dataframe(df_grupos_comp, hide_index=True, use_container_width=True)

        # Conclusão Operacional 100% Automatizada e Dinâmica
        df_ord_penal = df_grupos_comp.sort_values(by="Percentual Penal (%)", ascending=False)
        top1_penal = df_ord_penal.iloc[0]
        top2_penal = df_ord_penal.iloc[1]

        df_ord_vol = df_grupos_comp.sort_values(by="Total Ocorrências", ascending=False)
        top1_vol = df_ord_vol.iloc[0]
        top2_vol = df_ord_vol.iloc[1]
        top_social = df_grupos_comp.sort_values(by="Percentual Penal (%)", ascending=True).iloc[0]

        territorio_desc = regiao_escolhida if (regioes_escolhidas and len(regioes_escolhidas) == 1) else ("Regiões Selecionadas" if regioes_escolhidas else "Santa Catarina (Estado Inteiro)")

        conclusao_grupos = (
            f"💡 **Conclusão Operacional Automatizada ({label_periodo} | {territorio_desc}):**\n\n"
            f"• **Severidade Penal Relativa:** O grupo de **{top1_penal['Grupo Vulnerável']}** lidera a gravidade criminal no recorte ativo, "
            f"com **{top1_penal['Percentual Penal (%)']:.1f}%** das denúncias tipificadas como infrações penais (violência física, sexual ou ameaça), "
            f"seguido por **{top2_penal['Grupo Vulnerável']}** (**{top2_penal['Percentual Penal (%)']:.1f}%**), "
            f"demandando atuação prioritária de inquéritos policiais da PCSC e perícias da PCI-SC.\n\n"
            f"• **Volume Absoluto e Pressão Socioassistencial:** A maior sobrecarga operacional quantitativa recai sobre "
            f"**{top1_vol['Grupo Vulnerável']}** ({int(top1_vol['Total Ocorrências']):,} ocorrências) e "
            f"**{top2_vol['Grupo Vulnerável']}** ({int(top2_vol['Total Ocorrências']):,} ocorrências). "
            f"O grupo de **{top_social['Grupo Vulnerável']}** registra o maior contingente relativo de demandas socioassistenciais "
            f"({100.0 - top_social['Percentual Penal (%)']:.1f}%), vocacionado aos atendimentos dos Centros de Referência de Assistência Social (CRAS/CREAS)."
        ).replace(",", ".")

        st.info(conclusao_grupos)

    # -------------------------------------------------------------------------
    # ABA 3: CAPACIDADE PERICIAL FORENSE (PCI-SC)
    # -------------------------------------------------------------------------
    with tab_pci:
        st.subheader("Diagnóstico de Vulnerabilidade e Tempo de Resposta Forense")
        st.markdown("""
        Em infrações penais contra a dignidade sexual e agressões com lesão corporal, a preservação da prova material 
        depende do **tempo de deslocamento até a unidade da Polícia Científica (PCI-SC)** para exame de corpo de delito 
        e coleta do kit de DNA (janela crítica de até 72 horas).
        """)

        # Cálculos dinâmicos da malha de acesso à perícia forense
        muns_imediata = len(df_filtrado[df_filtrado["distancia_pci_km"] < 25.0])
        muns_atencao = len(df_filtrado[(df_filtrado["distancia_pci_km"] >= 25.0) & (df_filtrado["distancia_pci_km"] <= 50.0)])
        muns_vazio = len(df_filtrado[df_filtrado["distancia_pci_km"] > 50.0])

        col_z1, col_z2, col_z3 = st.columns(3)
        with col_z1:
            st.success(f"Zona de Resposta Imediata (< 25 km)\n\n**{muns_imediata} municípios** atendidos em menos de 30 minutos pelas superintendências ou núcleos regionais.")
        with col_z2:
            st.warning(f"Zona de Atenção Moderada (25 a 50 km)\n\n**{muns_atencao} municípios** com tempo estimado de 30 min a 1h por rodovias estaduais e vicinais.")
        with col_z3:
            st.error(f"Vazio Pericial Crítico (> 50 km)\n\n**{muns_vazio} municípios** com deslocamento superior a 1h15, sob risco de perda irrecuperável de vestígios de DNA.")

        st.markdown(f"### Municípios com Maior Pico Criminal Localizados em Distâncias Críticas (> 35 km da PCI) - {label_periodo}")
        df_vazio_calc = df_filtrado[df_filtrado["distancia_pci_km"] >= 35.0].sort_values(by="taxa_exibicao", ascending=False).head(6)

        if not df_vazio_calc.empty:
            df_vazio_tabela = df_vazio_calc[["municipio", "regiao_intermediaria", "populacao_censo_2022", col_penal, "taxa_exibicao", "distancia_pci_km", "pci_proxima"]].copy()
            df_vazio_tabela["distancia_pci_km"] = df_vazio_tabela["distancia_pci_km"].apply(lambda d: f"{d:.1f} km")
            df_vazio_tabela["taxa_exibicao"] = df_vazio_tabela["taxa_exibicao"].apply(lambda t: f"{t:.1f}")
            df_vazio_tabela["populacao_censo_2022"] = df_vazio_tabela["populacao_censo_2022"].apply(lambda p: f"{p:,}".replace(",", "."))
            df_vazio_tabela[col_penal] = df_vazio_tabela[col_penal].apply(lambda c: f"{int(c):,}".replace(",", "."))

            st.dataframe(
                df_vazio_tabela.rename(
                    columns={
                        "municipio": "Município",
                        "regiao_intermediaria": "Região Intermediária",
                        "populacao_censo_2022": "População",
                        col_penal: "Casos Penais",
                        "taxa_exibicao": f"Taxa ({label_escala})",
                        "distancia_pci_km": "Distância da PCI",
                        "pci_proxima": "Unidade Forense de Referência"
                    }
                ),
                hide_index=True,
                use_container_width=True
            )

            # Síntese Tática Automatizada
            top1_vazio = df_vazio_calc.iloc[0]
            top_nomes_vazio = ", ".join(df_vazio_calc["municipio"].head(3).tolist())
            dist_max = df_vazio_calc["distancia_pci_km"].max()

            solucao_dinamica = (
                f"🛡️ **Solução Tática Proposta Automatizada ({label_periodo}):**\n\n"
                f"No recorte territorial selecionado, o ponto de maior vulnerabilidade forense é **{top1_vazio['municipio']}** "
                f"({top1_vazio['distancia_pci_km']:.1f} km até a {top1_vazio['pci_proxima']}), com taxa criminal de "
                f"**{top1_vazio['taxa_exibicao']:.1f} ocorrências por {fator_pop//1000}k hab**.\n\n"
                f"**Ação Recomendada:** Estruturar **Postos Avançados de Coleta Forense (PACF)** em unidades hospitalares e UPAs "
                f"de referência próximas a **{top_nomes_vazio}**, integrando a Secretaria de Estado da Saúde (SES-SC) à Polícia Científica (PCI-SC). "
                f"Isso assegura a coleta de vestígios biológicos (kit de DNA em crimes sexuais e lesões graves) "
                f"dentro da janela clínica indispensável de até 72 horas, evitando o perecimento da prova pericial."
            )
            st.info(solucao_dinamica)
        else:
            st.success("Não foram identificados municípios em vazio pericial crítico com os filtros territoriais selecionados.")

        with st.expander("Catálogo das 30 Unidades da Polícia Científica de SC"):
            if not df_pci.empty:
                st.dataframe(
                    df_pci[["sigla", "nome", "municipio", "tipo", "jurisdicao"]].rename(
                        columns={
                            "sigla": "Sigla",
                            "nome": "Unidade Forense",
                            "municipio": "Município Sede",
                            "tipo": "Tipo de Unidade",
                            "jurisdicao": "Comarcas Atendidas"
                        }
                    ),
                    hide_index=True,
                    use_container_width=True
                )

    # -------------------------------------------------------------------------
    # ABA 4: MICRODADOS E TABELA ANALÍTICA DOS MUNICÍPIOS
    # -------------------------------------------------------------------------
    with tab_dados:
        st.subheader("Base de Dados dos 295 Municípios de Santa Catarina")

        st.markdown("Explore, filtre e pesquise os indicadores detalhados dos municípios de Santa Catarina com múltiplos critérios simultâneos.")

        # Painel de Filtros Avançados em Grid
        col_s1, col_s2, col_s3, col_s4 = st.columns([4, 3, 3, 3])
        with col_s1:
            busca = st.text_input("🔍 Pesquisar município, região ou código IBGE:", placeholder="Ex.: Chapecó, 4205407, Joinville...")
        with col_s2:
            filtro_porte = st.selectbox(
                "Porte Populacional (IBGE):",
                [
                    "Todos os Portes",
                    "Pequeno Porte I (< 20 mil hab)",
                    "Pequeno Porte II (20 mil a 50 mil hab)",
                    "Médio Porte (50 mil a 100 mil hab)",
                    "Grande Porte (> 100 mil hab)"
                ]
            )
        with col_s3:
            filtro_severidade = st.selectbox(
                "Perfil de Ocorrência:",
                [
                    "Todos os Perfis",
                    "Predomínio Penal (> 60% Crimes)",
                    "Predomínio Social (> 60% Rede SUAS)",
                    "Picos Acima da Média Estadual"
                ]
            )
        with col_s4:
            filtro_pci = st.selectbox(
                "Acesso Forense (PCI):",
                [
                    "Todas as Zonas",
                    "Vazios Críticos (> 50 km)",
                    "Atenção Moderada (25 a 50 km)",
                    "Resposta Imediata (< 25 km)"
                ]
            )

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
            st.metric("População Coberta", f"{pop_view:,}".replace(",", ".") + " hab")
        with rm3:
            st.metric("Volume de Denúncias", f"{casos_view:,}".replace(",", "."))
        with rm4:
            st.metric(f"Taxa Média do Recorte", f"{taxa_view:.1f} / {fator_pop//1000}k hab")

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
        df_tabela_formatada["População (2022)"] = df_tabela_formatada["População (2022)"].apply(lambda v: f"{int(v):,}".replace(",", "."))
        df_tabela_formatada["Total Ocorrências"] = df_tabela_formatada["Total Ocorrências"].apply(lambda v: f"{int(v):,}".replace(",", "."))
        df_tabela_formatada["Indício Penal"] = df_tabela_formatada["Indício Penal"].apply(lambda v: f"{int(v):,}".replace(",", "."))
        df_tabela_formatada["Demanda Social"] = df_tabela_formatada["Demanda Social"].apply(lambda v: f"{int(v):,}".replace(",", "."))
        df_tabela_formatada["% Penal"] = df_tabela_formatada["% Penal"].apply(lambda v: f"{v:.1f}%")
        df_tabela_formatada[f"Total ({label_escala})"] = df_tabela_formatada[f"Total ({label_escala})"].apply(lambda v: f"{v:.1f}")
        df_tabela_formatada[f"Penal ({label_escala})"] = df_tabela_formatada[f"Penal ({label_escala})"].apply(lambda v: f"{v:.1f}")
        df_tabela_formatada["Dist. PCI (km)"] = df_tabela_formatada["Dist. PCI (km)"].apply(lambda v: f"{v:.1f} km")

        st.dataframe(
            df_tabela_formatada,
            hide_index=True,
            use_container_width=True
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

    # -------------------------------------------------------------------------
    # ABA 5: METODOLOGIA JURÍDICA E FONTES OFICIAIS
    # -------------------------------------------------------------------------
    with tab_metodologia:
        st.subheader("Metodologia Jurídica e Rastreabilidade Governamental")

        st.markdown("""
        ### Distinção entre "Indício Penal" e "Demanda Socioassistencial"
        O Disque 100 (Disque Direitos Humanos) da Ouvidoria Nacional de Direitos Humanos recebe denúncias de natureza mista.
        Para dotar o Governo do Estado de Santa Catarina de capacidade decisória, foi implementada uma **triagem jurídica estrita**,
        separando demandas de persecução policial e perícia técnica daquelas vocacionadas ao acolhimento social.
        """)

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown("""
            #### 1. Indício de Infração Penal (Polícia Civil / Forense)
            - **Fundamentação Legal:**
              - Código Penal Brasileiro (Decreto-Lei nº 2.848/1940): Arts. 121 (Homicídio), 129 (Lesão Corporal), 136 (Maus-tratos), 213 (Estupro), 217-A (Estupro de Vulnerável).
              - Estatuto da Criança e do Adolescente (Lei nº 8.069/1990): Arts. 232 a 244-B (Crimes em espécie e pornografia infantil).
              - Lei Henry Borel (Lei nº 14.344/2022): Violência doméstica contra crianças e adolescentes.
              - Estatuto da Pessoa Idosa (Lei nº 10.741/2003): Arts. 96 a 108 (Discriminação, apropriação indébita e abandono material).
              - Lei Maria da Penha (Lei nº 11.340/2006): Violência de gênero.
            - **Destinação Institucional:** Envio de notícia-crime para as Delegacias da Polícia Civil (PCSC / DPCAMI) e requisição pericial à Polícia Científica de SC (PCI-SC).
            """)
        with col_m2:
            st.markdown("""
            #### 2. Demanda Socioassistencial (Rede SUAS)
            - **Fundamentação Legal:**
              - Lei Orgânica da Assistência Social - LOAS (Lei nº 8.742/1993).
              - Tipificação Nacional de Serviços Socioassistenciais (Resolução CNAS nº 109/2009).
              - Sistema Único de Assistência Social (SUAS).
            - **Caracterização:** Situações de vulnerabilidade socioeconômica, evasão escolar, desabrigamento voluntário, conflitos intrafamiliares leves e ausência de assistência básica não-dolosa.
            - **Destinação Institucional:** Acompanhamento familiar pelos Centros de Referência de Assistência Social (CRAS), Centros de Referência Especializados (CREAS) e Conselhos Tutelares.
            """)

        st.markdown("### Fontes Oficiais da Internet Governamental (Gov.br)")
        st.markdown("""
| Órgão / Portal | Link Oficial | Descrição |
| :--- | :--- | :--- |
| **Ministério dos Direitos Humanos e da Cidadania (MDHC)** | [https://www.gov.br/mdh/pt-br/ondh](https://www.gov.br/mdh/pt-br/ondh) | Painel de Dados da Ouvidoria Nacional de Direitos Humanos e microdados abertos do Disque 100. |
| **Ministério da Justiça e Segurança Pública (MJSP)** | [https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/senasp](https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/senasp) | Sistema Nacional de Informações de Segurança Pública (SENASP) e protocolos de investigação. |
| **Ministério do Desenvolvimento Social (MDS)** | [https://www.gov.br/mds/pt-br/acoes-e-programas/assistencia-social/unidades-de-atendimento/cras-e-creas](https://www.gov.br/mds/pt-br/acoes-e-programas/assistencia-social/unidades-de-atendimento/cras-e-creas) | Tipificação Nacional de Serviços Socioassistenciais e parâmetros de atendimento do CRAS/CREAS. |
| **Instituto Brasileiro de Geografia e Estatística (IBGE)** | [https://sidra.ibge.gov.br/tabela/4714](https://sidra.ibge.gov.br/tabela/4714) | Censo Demográfico 2022: População residente oficial dos 295 municípios catarinenses. |
| **Polícia Científica de Santa Catarina (PCI-SC)** | [https://www.policiacientifica.sc.gov.br](https://www.policiacientifica.sc.gov.br/) | Estrutura organizacional das 7 superintendências regionais e 23 núcleos periciais. |
| **Polícia Civil de Santa Catarina (PCSC)** | [https://www.pc.sc.gov.br](https://www.pc.sc.gov.br/) | Mapeamento das Delegacias de Proteção à Criança, Adolescente, Mulher e Idoso (DPCAMI). |
""")

        st.markdown("### Rastreabilidade Criptográfica (SHA-256)")
        st.markdown("""
        - `sc_fato_denuncias.parquet`: `5b57d76ec49b168a2bf18fbff0725a32ec4ca75a898a8a472c695b28d71228e9`
        - `sc_kpis_grupos_municipios.parquet`: `9a81ec387bfdc63b8ce885eb2e1b12b596d1945d81b85848cb8ce819611db18f`
        - Base Analítica: `sc_disque100_analitico.duckdb` (Formato colunar de alta performance, indexado por código IBGE)
        """)


if __name__ == "__main__":
    run_streamlit_app()
