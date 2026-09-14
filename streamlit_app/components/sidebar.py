"""
=============================================================================
Barra lateral: filtros e metadados
=============================================================================
Devolve um `Filtros`, com campos nomeados, em lugar da tupla posicional de
treze elementos usada antes.

O recorte temporal opera sobre a tabela por ano e semestre, de modo que o
painel sabe quantos semestres o periodo cobre e pode anualizar as taxas. Anos
com cobertura parcial sao sinalizados no proprio rotulo do controle.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from streamlit_app.config import (
    AJUDA_DISTANCIA,
    AJUDA_FOCOS,
    AJUDA_PCI_MAPA,
    AJUDA_RODOVIAS,
    AJUDA_POP_MINIMA,
    AJUDA_TAXA,
    AJUDA_UNIDADE,
    ESCALA_OPCOES,
    FOLIUM_TOPIC_MAP,
    Filtros,
    GRUPO_GERAL,
    GRUPO_OPCOES,
    NATUREZA_OPCOES,
    POP_MINIMA_OPCOES,
    POP_MINIMA_PADRAO,
    PRIMEIRO_ANO_COM_IDENTIFICADOR,
    UNIDADE_DENUNCIAS,
    UNIDADE_OPCOES,
)
from streamlit_app.utils.formatters import formatar_numero

MODO_ACUMULADO = "Todo o período"
MODO_ANO = "Um ano"
MODO_INTERVALO = "Intervalo de anos"

CHAVES_AGRUPAMENTO = [
    "ibge_code", "municipio", "regiao_intermediaria", "regiao_imediata", "populacao_censo_2022",
]


def _anos_disponiveis(df_ano: pd.DataFrame) -> List[int]:
    if df_ano.empty or "ano" not in df_ano.columns:
        return []
    return sorted(int(a) for a in df_ano["ano"].dropna().unique())


def _semestres_por_ano(df_ano: pd.DataFrame) -> Dict[int, int]:
    """
    Quantos semestres cada ano cobre.

    Os arquivos anuais de 2011 a 2019 vem com semestre 0 e representam o ano
    inteiro, portanto contam como dois semestres.
    """
    if df_ano.empty or "semestre" not in df_ano.columns:
        return {}
    contagem: Dict[int, int] = {}
    for ano, grupo in df_ano.groupby("ano"):
        semestres = set(int(s) for s in grupo["semestre"].dropna().unique())
        contagem[int(ano)] = 2 if semestres == {0} else len(semestres)
    return contagem


def _agregar(df_ano: pd.DataFrame, anos: List[int]) -> pd.DataFrame:
    """Soma a tabela por ano e semestre no recorte escolhido."""
    sub = df_ano[df_ano["ano"].isin(anos)]
    if sub.empty:
        return sub
    numericas = [
        c for c in sub.columns
        if c not in CHAVES_AGRUPAMENTO + ["ano", "semestre"]
        and pd.api.types.is_numeric_dtype(sub[c])
    ]
    return sub.groupby(CHAVES_AGRUPAMENTO, as_index=False, dropna=False)[numericas].sum()


def _rotulo_ano(ano: int, semestres: Dict[int, int]) -> str:
    return f"{ano} (parcial)" if semestres.get(ano, 2) < 2 else str(ano)


def render_sidebar(df_kpi: pd.DataFrame, df_ano: pd.DataFrame, metadados: Dict[str, Any]) -> Tuple[pd.DataFrame, Filtros]:
    """Renderiza os filtros e devolve a base recortada e o estado dos filtros."""
    f = Filtros()
    anos = _anos_disponiveis(df_ano)
    semestres_por_ano = _semestres_por_ano(df_ano)

    st.sidebar.markdown("### Filtros")

    if st.sidebar.button("Restaurar filtros", width="stretch"):
        for chave in list(st.session_state.keys()):
            if chave.startswith("f_"):
                del st.session_state[chave]
        st.rerun()

    # -------------------------------------------------------------------------
    # Período
    # -------------------------------------------------------------------------
    with st.sidebar.expander("Período", expanded=True):
        modo = st.radio(
            "Recorte temporal",
            [MODO_ACUMULADO, MODO_ANO, MODO_INTERVALO],
            key="f_modo",
            label_visibility="collapsed",
        )

        if modo == MODO_ANO and anos:
            ano = st.select_slider(
                "Ano",
                options=anos,
                value=max(a for a in anos if semestres_por_ano.get(a, 2) == 2) if anos else anos[-1],
                format_func=lambda a: _rotulo_ano(a, semestres_por_ano),
                key="f_ano",
            )
            f.modo_temporal, f.ano = "ano", int(ano)
            f.anos_no_recorte = [int(ano)]
            f.label_periodo = str(ano)
            f.year_param = str(ano)
        elif modo == MODO_INTERVALO and len(anos) > 1:
            inicio, fim = st.slider(
                "Intervalo",
                min_value=min(anos),
                max_value=max(anos),
                value=(max(min(anos), PRIMEIRO_ANO_COM_IDENTIFICADOR), max(anos)),
                key="f_intervalo",
            )
            f.modo_temporal, f.intervalo = "intervalo", (int(inicio), int(fim))
            f.anos_no_recorte = [a for a in anos if inicio <= a <= fim]
            f.label_periodo = f"{inicio} a {fim}"
            f.year_param = f"{inicio}-{fim}"
        else:
            f.modo_temporal = "acumulado"
            f.anos_no_recorte = list(anos)
            f.label_periodo = f"{min(anos)} a {max(anos)}" if anos else "período completo"
            f.year_param = "all"

        f.semestres_no_recorte = sum(semestres_por_ano.get(a, 2) for a in f.anos_no_recorte)
        f.recorte_tem_ano_parcial = any(
            semestres_por_ano.get(a, 2) < 2 for a in f.anos_no_recorte
        )
        if f.recorte_tem_ano_parcial:
            parciais = [a for a in f.anos_no_recorte if semestres_por_ano.get(a, 2) < 2]
            st.caption(
                "Cobertura parcial em "
                + ", ".join(str(a) for a in parciais)
                + ". As taxas são anualizadas; os totais absolutos não.",
            )

    # -------------------------------------------------------------------------
    # Recorte analítico
    # -------------------------------------------------------------------------
    with st.sidebar.expander("Recorte", expanded=True):
        unidade_escolhida = st.radio(
            "Unidade de medida",
            list(UNIDADE_OPCOES.keys()),
            key="f_unidade",
            help=AJUDA_UNIDADE,
        )
        f.unidade = UNIDADE_OPCOES[unidade_escolhida]

        natureza_escolhida = st.radio(
            "Natureza da ocorrência",
            list(NATUREZA_OPCOES.keys()),
            key="f_natureza",
        )
        f.natureza = NATUREZA_OPCOES[natureza_escolhida]

        grupo_escolhido = st.selectbox(
            "Grupo vulnerável",
            list(GRUPO_OPCOES.keys()),
            key="f_grupo",
        )
        f.grupo = GRUPO_OPCOES[grupo_escolhido]

        if f.unidade == UNIDADE_DENUNCIAS and f.grupo != GRUPO_GERAL:
            st.caption(
                "A contagem de denúncias únicas não é decomposta por grupo vulnerável. "
                "Este recorte usa registros de violação."
            )

    # -------------------------------------------------------------------------
    # Território
    # -------------------------------------------------------------------------
    with st.sidebar.expander("Território", expanded=True):
        regioes = sorted(df_kpi["regiao_intermediaria"].dropna().unique().tolist()) if not df_kpi.empty else []
        f.regioes = st.multiselect(
            f"Regiões intermediárias (vazio: todas as {len(regioes)})",
            options=regioes,
            default=[],
            key="f_regioes",
        )
        f.region_code = f.regioes[0] if len(f.regioes) == 1 else "all"

        escala = st.radio(
            "Escala da taxa",
            list(ESCALA_OPCOES.keys()),
            key="f_escala",
            help=AJUDA_TAXA,
        )
        f.fator_pop = ESCALA_OPCOES[escala]

        f.pop_minima = st.select_slider(
            "População mínima no ranking por taxa",
            options=POP_MINIMA_OPCOES,
            value=POP_MINIMA_PADRAO,
            format_func=lambda v: "sem piso" if v == 0 else f"{formatar_numero(v)} hab.",
            key="f_pop_minima",
            help=AJUDA_POP_MINIMA,
        )

    # -------------------------------------------------------------------------
    # Camadas do mapa
    # -------------------------------------------------------------------------
    with st.sidebar.expander("Camadas do mapa", expanded=True):
        f.camada_rodovias = st.checkbox(
            "Eixos rodoviários", value=True, key="f_rodovias", help=AJUDA_RODOVIAS
        )
        f.camada_pci = st.checkbox(
            "Unidades da Polícia Científica", value=True, key="f_pci", help=AJUDA_PCI_MAPA
        )
        f.camada_focos = st.checkbox(
            "Pontos de foco", value=True, key="f_focos", help=AJUDA_FOCOS
        )
        if f.camada_focos:
            f.quantidade_focos = st.slider(
                "Quantos focos destacar", min_value=5, max_value=25, value=10, step=5,
                key="f_qtd_focos",
            )
        f.camada_clusters = st.checkbox(
            "Agrupamentos no mapa detalhado", value=True, key="f_clusters",
            help="Aplica-se somente ao mapa Folium pré-gerado, no fim da aba Território.",
        )

    # -------------------------------------------------------------------------
    # Metadados, lidos do relatório de auditoria
    # -------------------------------------------------------------------------
    st.sidebar.divider()
    with st.sidebar.expander("Sobre a base", expanded=False):
        linhas = []
        if metadados.get("periodo"):
            linhas.append(f"Período: {metadados['periodo']}")
        if metadados.get("registros") is not None:
            linhas.append(f"Registros de violação: {formatar_numero(metadados['registros'])}")
        if metadados.get("denuncias_unicas") is not None:
            linhas.append(f"Denúncias únicas apuráveis: {formatar_numero(metadados['denuncias_unicas'])}")
        if metadados.get("populacao") is not None:
            linhas.append(
                f"População: {formatar_numero(metadados['populacao'])} hab. "
                f"em {metadados.get('municipios', 0)} municípios (Censo 2022)"
            )
        if metadados.get("composicao_pci"):
            comp = ", ".join(
                f"{v} {k.lower()}" for k, v in sorted(metadados["composicao_pci"].items())
            )
            linhas.append(f"Polícia Científica: {metadados.get('unidades_pci')} unidades ({comp})")
        if metadados.get("atualizado_em"):
            linhas.append(f"Processado em: {metadados['atualizado_em']}")
        st.caption("  \n".join(linhas) if linhas else "Relatório de auditoria não encontrado.")

    # -------------------------------------------------------------------------
    # Base recortada
    # -------------------------------------------------------------------------
    if f.modo_temporal == "acumulado" or df_ano.empty:
        base = df_kpi.copy()
        if f.modo_temporal != "acumulado" and df_ano.empty:
            st.sidebar.error(
                "A tabela por ano não foi encontrada. Exibindo o período completo. "
                "Execute scripts/build_annual_kpis.py."
            )
            f.modo_temporal = "acumulado"
            f.label_periodo = metadados.get("periodo") or "período completo"
            f.year_param = "all"
    else:
        base = _agregar(df_ano, f.anos_no_recorte)
        if base.empty:
            st.sidebar.warning("Nenhum registro no período selecionado.")

    if f.regioes and not base.empty:
        base = base[base["regiao_intermediaria"].isin(f.regioes)].copy()

    return base, f


def topico_folium(filtros: Filtros) -> str:
    return FOLIUM_TOPIC_MAP.get(filtros.grupo, "total")
