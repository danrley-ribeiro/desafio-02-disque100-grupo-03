"""
=============================================================================
Cartoes de resumo do recorte ativo
=============================================================================
Os rotulos declaram a unidade de medida em uso. Antes, o primeiro cartao dizia
"Total de Ocorrencias" com a dica "total acumulado de denuncias", quando o
numero exibido era de registros de violacao.

No nivel da denuncia, "com indicio penal" significa "com ao menos uma violacao
tipificada", e essa proporcao chega a 95%, contra 61% medidos em registros de
violacao. Nao e divergencia: sao perguntas diferentes. O cartao diz qual das
duas esta respondendo e exibe a predominancia penal, que e a medida de
denuncia comparavel a proporcao apurada em violacoes.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from streamlit_app.config import (
    AJUDA_PENAL,
    AJUDA_PENAL_DENUNCIA,
    AJUDA_PREDOMINANCIA,
    AJUDA_SOCIAL,
    AJUDA_TAXA,
    Filtros,
    ROTULO_PENAL_POR_UNIDADE,
    ROTULO_SOCIAL_POR_UNIDADE,
    UNIDADE_DENUNCIAS,
    UNIDADE_ROTULO,
)
from streamlit_app.utils.formatters import (
    formatar_numero,
    formatar_percentual,
    formatar_taxa,
)


def render_kpi_cards(resumo: Dict[str, Any], filtros: Filtros) -> None:
    """Renderiza os quatro cartoes de resumo do recorte."""
    unidade = filtros.unidade_efetiva()
    e_denuncia = unidade == UNIDADE_DENUNCIAS
    rotulo_unidade = UNIDADE_ROTULO[unidade]

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            label=rotulo_unidade.capitalize(),
            value=formatar_numero(resumo["total"]),
            help=(
                "Denúncias distintas no recorte, contadas pelo identificador oficial."
                if e_denuncia
                else "Linhas dos microdados: combinações de violação, vítima e suspeito."
            ),
        )
        fator = resumo.get("fator_expansao")
        if e_denuncia and fator:
            st.caption(f"{formatar_taxa(fator)} registros de violação por denúncia")

    with c2:
        st.metric(
            label=ROTULO_PENAL_POR_UNIDADE[unidade],
            value=formatar_numero(resumo["penal"]),
            delta=f"{formatar_percentual(resumo['pct_penal'])} do total",
            delta_color="off",
            help=AJUDA_PENAL_DENUNCIA if e_denuncia else AJUDA_PENAL,
        )
        if e_denuncia and resumo.get("pct_maioria_penal"):
            st.caption(
                f"Predominância penal: {formatar_percentual(resumo['pct_maioria_penal'])} "
                f"({formatar_numero(resumo['maioria_penal'])})",
                help=AJUDA_PREDOMINANCIA,
            )

    with c3:
        st.metric(
            label=ROTULO_SOCIAL_POR_UNIDADE[unidade],
            value=formatar_numero(resumo["social"]),
            delta=f"{formatar_percentual(resumo['pct_social'])} do total",
            delta_color="off",
            help=AJUDA_SOCIAL,
        )

    with c4:
        cobertura = resumo["semestres"] / 2
        st.metric(
            label=f"Taxa anual {filtros.rotulo_escala}",
            value=formatar_taxa(resumo["taxa"]),
            delta=f"penal: {formatar_taxa(resumo['taxa_penal'])}",
            delta_color="off",
            help=(
                AJUDA_TAXA
                + f" Base deste recorte: {formatar_numero(resumo['populacao'])} habitantes "
                + f"e {formatar_taxa(cobertura)} ano(s) de cobertura."
            ),
        )
