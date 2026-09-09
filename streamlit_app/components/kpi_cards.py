"""
Componente dos 4 Cards Executivos de Resumo com Deltas e Tooltips Jurídicos.
"""

import streamlit as st
from streamlit_app.config import HELP_PENAL, HELP_SOCIAL
from streamlit_app.utils.formatters import format_brazilian


def render_kpi_cards(
    total_casos: int,
    total_penal: int,
    total_social: int,
    pct_penal: float,
    pct_social: float,
    taxa_media_pop: float,
    taxa_media_penal: float,
    label_periodo: str,
    label_escala: str,
    fator_pop: int
) -> None:
    """Renderiza os 4 cards de KPIs estratégicos no topo do painel."""
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.metric(
            label=f"Total de Ocorrências ({label_periodo})",
            value=format_brazilian(total_casos),
            help="Total acumulado de denúncias no grupo e território selecionados."
        )

    with kpi2:
        st.metric(
            label="Indício Penal (Crimes)",
            value=format_brazilian(total_penal),
            delta=f"{pct_penal:.1f}% do volume",
            help=HELP_PENAL
        )

    with kpi3:
        st.metric(
            label="Demanda Socioassistencial",
            value=format_brazilian(total_social),
            delta=f"{pct_social:.1f}% do volume",
            delta_color="off",
            help=HELP_SOCIAL
        )

    with kpi4:
        st.metric(
            label=f"Média {label_escala}",
            value=f"{taxa_media_pop:.1f}",
            delta=f"Penal: {taxa_media_penal:.1f}",
            delta_color="off",
            help=f"Taxa proporcional calculada com base na população oficial do Censo IBGE 2022 para {fator_pop:,} habitantes.".replace(",", ".")
        )

    st.markdown("---")

