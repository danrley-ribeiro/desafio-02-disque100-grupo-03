"""
=============================================================================
Aba Grupos: comparacao entre os grupos vulneraveis
=============================================================================
A tabela e montada por um laco sobre os grupos definidos em `config`, no lugar
das cinquenta linhas de dicionario literal com trinta e seis chamadas de soma
que existiam antes, cujos rotulos divergiam dos usados na barra lateral e no
mapa.

Duas correcoes de conteudo, e nao apenas de forma:

  1. Entra a linha "Sem grupo identificado". Os registros que nao pertencem a
     nenhum dos seis grupos simplesmente desapareciam desta aba, embora sejam
     dezenas de milhares.

  2. A aba declara que os grupos nao sao mutuamente exclusivos e mostra, para
     cada grupo, desde quando a serie e comparavel. O modulo "Violencia contra
     a Mulher" so existe nos microdados a partir de 2025; antes disso a
     marcacao depende de inferencia por genero e relacao vitima-suspeito, de
     modo que a serie desse grupo nao mede a mesma coisa ao longo do tempo.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from streamlit_app.config import (
    AVISO_GRUPOS_NAO_EXCLUSIVOS,
    CATEGORICA,
    COR_PENAL,
    COR_SOCIAL,
    Filtros,
    GRUPO_BASE_LEGAL,
    GRUPO_FLAG,
    GRUPO_ROTULOS,
)
from streamlit_app.utils.charts import barras_empilhadas, barras_horizontais
from streamlit_app.utils.formatters import (
    formatar_numero,
    formatar_percentual,
    formatar_taxa,
)

ROTULO_SEM_GRUPO = "Sem grupo identificado"


def render_tab_grupos(df: pd.DataFrame, filtros: Filtros, metadados: Dict[str, Any]) -> None:
    if df.empty:
        st.info("Nenhum município no recorte selecionado.")
        return

    st.subheader("Grupos vulneráveis")
    st.caption(
        f"Comparação no período {filtros.label_periodo}, em {filtros.rotulo_territorio}. "
        "Contagem em registros de violação, a única unidade decomposta por grupo."
    )
    st.info(AVISO_GRUPOS_NAO_EXCLUSIVOS, icon=None)

    tabela = _montar_tabela(df, filtros)
    if tabela.empty:
        st.info("Sem dados de grupo neste recorte.")
        return
    tabela = _injetar_comparavel(tabela, metadados)

    # -------------------------------------------------------------------------
    # Composicao e severidade
    # -------------------------------------------------------------------------
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Composição das ocorrências**")
        st.caption("Indício penal e demanda socioassistencial em cada grupo.")
        st.plotly_chart(
            barras_empilhadas(
                tabela.sort_values("total"),
                coluna_categoria="Grupo",
                series=[
                    ("penal", "Indício de infração penal", COR_PENAL),
                    ("social", "Demanda socioassistencial", COR_SOCIAL),
                ],
                rotulo_valor="Registros de violação",
            ),
            width="stretch",
            key="grupos_composicao",
        )

    with col_b:
        st.markdown("**Proporção com indício penal**")
        st.caption("Fração das ocorrências do grupo que a taxonomia tipifica como penal.")
        st.plotly_chart(
            barras_horizontais(
                tabela,
                coluna_categoria="Grupo",
                coluna_valor="pct_penal",
                rotulo_valor="Percentual com indício penal",
                cor=CATEGORICA[0],
                sufixo_dica="%",
                colunas_extra={"total": "Registros"},
            ),
            width="stretch",
            key="grupos_severidade",
        )

    # -------------------------------------------------------------------------
    # Tabela
    # -------------------------------------------------------------------------
    st.markdown("**Quadro comparativo**")
    exibicao = pd.DataFrame({
        "Grupo": tabela["Grupo"],
        "Registros": tabela["total"].map(formatar_numero),
        "Indício penal": tabela["penal"].map(formatar_numero),
        "Demanda social": tabela["social"].map(formatar_numero),
        "% penal": tabela["pct_penal"].map(formatar_percentual),
        f"Taxa anual {filtros.rotulo_escala}": tabela["taxa"].map(formatar_taxa),
        "Comparável desde": tabela["comparavel_desde"],
        "Base legal": tabela["base_legal"],
    })
    st.dataframe(exibicao, hide_index=True, width="stretch")

    total_recorte = int(df["valor_total"].sum())
    soma_grupos = int(tabela[tabela["Grupo"] != ROTULO_SEM_GRUPO]["total"].sum())
    st.caption(
        f"A soma dos seis grupos é {formatar_numero(soma_grupos)}, contra "
        f"{formatar_numero(total_recorte)} registros no recorte. A diferença vem da "
        "sobreposição entre grupos e dos registros sem grupo identificado, listados na "
        "última linha."
    )

    _render_comparabilidade(tabela, metadados)


def _montar_tabela(df: pd.DataFrame, filtros: Filtros) -> pd.DataFrame:
    """Agrega cada grupo em uma linha, mais a linha de registros sem grupo."""
    populacao = df["populacao_censo_2022"].sum()
    anos = max(filtros.semestres_no_recorte, 1) / 2.0

    linhas: List[Dict[str, Any]] = []
    for chave, rotulo in GRUPO_ROTULOS.items():
        col_total, col_penal = f"{chave}_total", f"{chave}_penal"
        if col_total not in df.columns:
            continue
        total = int(df[col_total].fillna(0).sum())
        penal = int(df[col_penal].fillna(0).sum()) if col_penal in df.columns else 0
        linhas.append({
            "Grupo": rotulo,
            "chave": chave,
            "total": total,
            "penal": penal,
            "social": total - penal,
            "pct_penal": (penal / total * 100.0) if total else None,
            "taxa": (total / populacao / anos * filtros.fator_pop) if populacao else None,
            "base_legal": GRUPO_BASE_LEGAL.get(chave, ""),
        })

    if "sem_grupo_total" in df.columns:
        total = int(df["sem_grupo_total"].fillna(0).sum())
        penal = int(df["sem_grupo_penal"].fillna(0).sum()) if "sem_grupo_penal" in df.columns else 0
        linhas.append({
            "Grupo": ROTULO_SEM_GRUPO,
            "chave": "sem_grupo",
            "total": total,
            "penal": penal,
            "social": total - penal,
            "pct_penal": (penal / total * 100.0) if total else None,
            "taxa": (total / populacao / anos * filtros.fator_pop) if populacao else None,
            "base_legal": "Sem público específico declarado na denúncia",
        })

    return pd.DataFrame(linhas).sort_values("total", ascending=False).reset_index(drop=True)


def _render_comparabilidade(tabela: pd.DataFrame, metadados: Dict[str, Any]) -> None:
    """Declara desde quando cada serie de grupo e comparavel."""
    comparabilidade = (metadados.get("comparabilidade") or {}).get("por_grupo", {})
    if not comparabilidade:
        return

    avisos = []
    for chave, rotulo in GRUPO_ROTULOS.items():
        info = comparabilidade.get(GRUPO_FLAG[chave], {})
        desde = info.get("comparavel_desde")
        if desde and int(desde) > 2011:
            avisos.append(
                f"**{rotulo}**: o módulo próprio aparece nos microdados a partir de "
                f"{desde}. Antes disso a marcação depende de inferência, e a série do "
                "grupo não mede a mesma coisa ao longo do tempo."
            )

    anos_sem_coluna = (metadados.get("comparabilidade") or {}).get("anos_sem_coluna_de_grupo", [])
    if anos_sem_coluna:
        avisos.append(
            "Em "
            + ", ".join(str(a) for a in anos_sem_coluna)
            + ", parte dos arquivos não traz a coluna de grupo vulnerável; nesses "
            "períodos a atribuição depende apenas de faixa etária, deficiência e "
            "orientação sexual, e a linha sem grupo identificado é maior."
        )

    if avisos:
        with st.expander("Comparabilidade das séries por grupo", expanded=False):
            for a in avisos:
                st.markdown(f"- {a}")


def _injetar_comparavel(tabela: pd.DataFrame, metadados: Dict[str, Any]) -> pd.DataFrame:
    """Acrescenta a coluna de comparabilidade lida do relatorio de auditoria."""
    comparabilidade = (metadados.get("comparabilidade") or {}).get("por_grupo", {})
    tabela["comparavel_desde"] = tabela["chave"].map(
        lambda c: str(
            comparabilidade.get(GRUPO_FLAG.get(c, ""), {}).get("comparavel_desde") or "—"
        )
    )
    return tabela
