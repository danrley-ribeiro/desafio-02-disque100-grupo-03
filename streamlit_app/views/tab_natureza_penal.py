"""
=============================================================================
Aba Natureza penal: categoria, grau de indicio e orgao de encaminhamento
=============================================================================
Aba nova. A tabela `fato_denuncias` sempre carregou `categoria_penal`,
`grau_certeza`, `orgao_prioritario` e `fundamentacao_legal`, e nenhum desses
quatro campos aparecia no painel: as tabelas de KPI simplesmente nao os
levavam adiante.

Aqui eles respondem a pergunta operacional que o painel existia para responder
e nao respondia: dado o recorte, que tipo de crime predomina, com que grau de
indicio, e para qual orgao a ocorrencia deveria seguir.

O grau de indicio e atributo da regra da taxonomia, nao estimativa estatistica
de confianca. A aba diz isso onde o numero aparece.
=============================================================================
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import streamlit as st

from streamlit_app.config import CATEGORICA, Filtros
from streamlit_app.utils.charts import (
    ALTURA_PADRAO,
    barras_horizontais,
    series_temporal,
)
from streamlit_app.utils.formatters import formatar_numero, formatar_percentual

CATEGORIA_SOCIAL = "REDE_DE_PROTECAO_SOCIAL"

# Rotulos legiveis para as categorias da taxonomia.
ROTULO_CATEGORIA = {
    "CRIMES_CONTRA_A_VIDA": "Crimes contra a vida",
    "CRIMES_SEXUAIS": "Crimes sexuais",
    "CRIMES_INTEGRIDADE_FISICA_E_TORTURA": "Integridade física e tortura",
    "CRIMES_CONTRA_A_LIBERDADE_INDIVIDUAL": "Liberdade individual e tráfico",
    "CRIMES_DE_AMEACA_E_COACAO": "Ameaça e coação",
    "CRIMES_CONTRA_A_HONRA_E_PRECONCEITO": "Honra, racismo e preconceito",
    "CRIMES_DE_ABANDONO_E_OMISSAO": "Abandono e omissão de socorro",
    "CRIMES_PATRIMONIAIS_E_FINANCEIROS": "Patrimoniais e financeiros",
    "VIOLENCIA_PSICOLOGICA_CONTRA_MULHER": "Violência psicológica contra mulher",
    "VIOLENCIA_PSICOLOGICA_CONTRA_IDOSO": "Violência psicológica contra pessoa idosa",
    "INFRACAO_PENAL_REFUGIO_FLAGRANTE_OU_RISCO_IMINENTE": "Flagrante ou risco iminente",
    "INFRACAO_PENAL_REFUGIO_CUSTODIA_PRISIONAL_ATIVA": "Custódia prisional ativa",
    "INFRACAO_PENAL_REFUGIO_CENARIO_POLICIAL_OU_PRISIONAL": "Cenário policial ou prisional",
    CATEGORIA_SOCIAL: "Rede de proteção social",
}

ROTULO_GRAU = {
    "ALTO": "Alto: tipo penal nomeado no relato",
    "MEDIO": "Médio: tipo penal dependente de contexto",
    "BAIXO": "Sem tipicidade penal reconhecida",
}

ROTULO_ORGAO = {
    "DELEGACIA_DE_HOMICIDIOS_OU_POLICIA_CIVIL": "Delegacia de Homicídios ou Polícia Civil",
    "DELEGACIA_ESPECIALIZADA_E_POLICIA_CIENTIFICA": "Delegacia especializada e Polícia Científica",
    "POLICIA_CIVIL_E_POLICIA_CIENTIFICA": "Polícia Civil e Polícia Científica",
    "POLICIA_CIVIL_OU_FEDERAL": "Polícia Civil ou Federal",
    "POLICIA_CIVIL_OU_MILITAR": "Polícia Civil ou Militar",
    "DELEGACIA_DE_POLICIA_CIVIL": "Delegacia de Polícia Civil",
    "DELEGACIA_DE_POLICIA_E_MINISTERIO_PUBLICO": "Delegacia de Polícia e Ministério Público",
    "DELEGACIA_DA_MULHER_DPCAMI": "Delegacia da Mulher (DPCAMI)",
    "MINISTERIO_PUBLICO_E_CONSELHO_TUTELAR": "Ministério Público e Conselho Tutelar",
    "REDE_SOCIOASSISTENCIAL_CRAS_CREAS_E_CONSELHO": "Rede socioassistencial (CRAS, CREAS e Conselho Tutelar)",
}


def render_tab_natureza_penal(df_cat: pd.DataFrame, filtros: Filtros) -> None:
    if df_cat.empty:
        st.warning(
            "Tabela `kpis_categoria_penal` não encontrada. Execute "
            "`python3 scripts/gerar_banco_duckdb_sc.py`."
        )
        return

    sub = _recortar(df_cat, filtros)
    if sub.empty:
        st.info("Nenhuma ocorrência no recorte selecionado.")
        return

    st.subheader("Natureza da ocorrência")
    st.caption(
        f"Período {filtros.label_periodo}, {filtros.rotulo_territorio}. "
        "Classificação automatizada por taxonomia de palavras-chave sobre o texto da "
        "violação relatada; indica onde há indício a apurar, não decisão jurídica. "
        "Esta aba conta sempre registros de violação, e inclui os registros sem município "
        "identificado quando nenhuma região está selecionada, por isso o total pode superar "
        "o dos cartões acima."
    )

    penal = sub[sub["indicio_penal"] == 1]
    total_registros = int(sub["registros"].sum())
    total_penal = int(penal["registros"].sum())

    c1, c2, c3 = st.columns(3)
    c1.metric("Registros no recorte", formatar_numero(total_registros))
    c2.metric(
        "Com indício penal",
        formatar_numero(total_penal),
        delta=formatar_percentual(total_penal / total_registros * 100 if total_registros else None),
        delta_color="off",
    )
    alto = int(penal[penal["grau_certeza"] == "ALTO"]["registros"].sum())
    c3.metric(
        "Indício de grau alto",
        formatar_numero(alto),
        delta=f"{formatar_percentual(alto / total_penal * 100 if total_penal else None)} do penal",
        delta_color="off",
        help=(
            "Grau alto significa que o relato nomeia diretamente um tipo penal. É um "
            "atributo da regra da taxonomia, não uma estimativa estatística de confiança."
        ),
    )

    st.divider()

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Categorias penais**")
        st.caption("Distribuição das ocorrências com indício penal por categoria da taxonomia.")
        por_cat = (
            penal.groupby("categoria_penal", as_index=False)["registros"].sum()
            .assign(rotulo=lambda d: d["categoria_penal"].map(lambda c: ROTULO_CATEGORIA.get(c, c)))
            .nlargest(12, "registros")
        )
        st.plotly_chart(
            barras_horizontais(
                por_cat,
                coluna_categoria="rotulo",
                coluna_valor="registros",
                rotulo_valor="Registros",
                cor=CATEGORICA[0],
            ),
            width="stretch",
            key="cat_penal",
        )

    with col_b:
        st.markdown("**Órgão de encaminhamento prioritário**")
        st.caption(
            "Destino indicado pela taxonomia para cada categoria. Orienta a triagem, "
            "não substitui a decisão de encaminhamento."
        )
        por_orgao = (
            sub.groupby("orgao_prioritario", as_index=False)["registros"].sum()
            .assign(rotulo=lambda d: d["orgao_prioritario"].map(lambda o: ROTULO_ORGAO.get(o, o)))
            .nlargest(12, "registros")
        )
        st.plotly_chart(
            barras_horizontais(
                por_orgao,
                coluna_categoria="rotulo",
                coluna_valor="registros",
                rotulo_valor="Registros",
                cor=CATEGORICA[2],
            ),
            width="stretch",
            key="cat_orgao",
        )

    # -------------------------------------------------------------------------
    # Evolucao das categorias no tempo
    # -------------------------------------------------------------------------
    if sub["ano"].nunique() > 1:
        st.markdown("**Evolução das principais categorias**")
        st.caption(
            "A proporção entre categorias muda quando muda o vocabulário de violação dos "
            "microdados, e não só quando muda a demanda. Compare com cautela entre eras."
        )
        principais = por_cat.nlargest(4, "registros")["categoria_penal"].tolist()
        serie = (
            penal[penal["categoria_penal"].isin(principais)]
            .pivot_table(index="ano", columns="categoria_penal", values="registros", aggfunc="sum")
            .fillna(0)
            .reset_index()
        )
        series_config = [
            (c, ROTULO_CATEGORIA.get(c, c), CATEGORICA[i % len(CATEGORICA)])
            for i, c in enumerate(principais)
            if c in serie.columns
        ]
        if series_config:
            st.plotly_chart(
                series_temporal(
                    serie,
                    coluna_x="ano",
                    series=series_config,
                    rotulo_valor="Registros",
                    titulo_x="Ano",
                ),
                width="stretch",
                key="cat_serie",
            )

    # -------------------------------------------------------------------------
    # Fundamentacao legal
    # -------------------------------------------------------------------------
    with st.expander("Fundamentação legal por categoria"):
        legal = (
            penal.groupby(["categoria_penal", "grau_certeza", "fundamentacao_legal"], as_index=False)["registros"]
            .sum()
            .sort_values("registros", ascending=False)
        )
        st.dataframe(
            pd.DataFrame({
                "Categoria": legal["categoria_penal"].map(lambda c: ROTULO_CATEGORIA.get(c, c)),
                "Grau do indício": legal["grau_certeza"].map(lambda g: ROTULO_GRAU.get(g, g)),
                "Fundamentação": legal["fundamentacao_legal"],
                "Registros": legal["registros"].map(formatar_numero),
            }),
            hide_index=True,
            width="stretch",
        )


def _recortar(df_cat: pd.DataFrame, filtros: Filtros) -> pd.DataFrame:
    sub = df_cat
    if filtros.anos_no_recorte:
        sub = sub[sub["ano"].isin(filtros.anos_no_recorte)]
    if filtros.regioes:
        sub = sub[sub["regiao_intermediaria"].isin(filtros.regioes)]
    return sub
