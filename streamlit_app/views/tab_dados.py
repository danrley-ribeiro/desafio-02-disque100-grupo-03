"""
=============================================================================
Aba Dados: tabela municipal, filtros cruzados e exportacao
=============================================================================
Correcoes de comportamento em relacao a versao anterior:

  - a ordenacao alfabetica estava invertida: escolher "decrescente" ordenava
    de A a Z;
  - o filtro "acima da media" comparava a taxa exibida, que pode ser penal ou
    socioassistencial, contra uma media sempre calculada no total;
  - os titulos afirmavam "295 municipios" mesmo quando o recorte por ano ou
    por regiao trazia menos;
  - `st.dataframe` recebia `use_container_width` e `width` ao mesmo tempo.
=============================================================================
"""

from __future__ import annotations

import io
from typing import Dict, List

import pandas as pd
import streamlit as st

from streamlit_app.config import (
    FAIXA_DISTANTE,
    FAIXA_INTERMEDIARIA,
    FAIXA_PROXIMA,
    Filtros,
    PERFIL_OPCOES,
    PORTE_OPCOES,
    UNIDADE_ROTULO,
    ZONA_PCI_OPCOES,
)
from streamlit_app.utils.formatters import (
    SEM_DADO,
    formatar_km,
    formatar_numero,
    formatar_percentual,
    formatar_taxa,
)

DICIONARIO_COLUNAS: Dict[str, str] = {
    "Município": "Nome oficial do município, IBGE.",
    "Região intermediária": "Divisão regional do IBGE de 2017; Santa Catarina tem sete.",
    "População": "População residente no Censo Demográfico 2022, tabela SIDRA 4714.",
    "Total": "Contagem na unidade de medida ativa, no período e grupo selecionados.",
    "Indício penal": "Subconjunto do total que a taxonomia tipifica como infração penal.",
    "Demanda social": "Total menos indício penal.",
    "% penal": "Indício penal dividido pelo total do município.",
    "Taxa total": "Total anualizado por habitante, na escala escolhida.",
    "Taxa penal": "Indício penal anualizado por habitante, na escala escolhida.",
    "Distância da PCI": "Distância geodésica em linha reta até a unidade pericial mais próxima.",
    "Unidade pericial": "Unidade da Polícia Científica mais próxima em linha reta.",
}


def render_tab_dados(df: pd.DataFrame, filtros: Filtros) -> None:
    if df.empty:
        st.info("Nenhum município no recorte selecionado.")
        return

    unidade = UNIDADE_ROTULO[filtros.unidade_efetiva()]
    st.subheader(f"Tabela municipal — {len(df)} municípios no recorte")
    st.caption(
        f"Período {filtros.label_periodo}, {filtros.rotulo_territorio}, "
        f"grupo {filtros.rotulo_grupo.lower()}, contagem em {unidade}."
    )

    # -------------------------------------------------------------------------
    # Filtros da aba
    # -------------------------------------------------------------------------
    c1, c2, c3, c4 = st.columns([4, 3, 3, 3])
    busca = c1.text_input(
        "Pesquisar",
        placeholder="município, região ou código IBGE",
        key="d_busca",
    )
    porte = c2.selectbox("Porte populacional", PORTE_OPCOES, key="d_porte")
    perfil = c3.selectbox("Perfil da ocorrência", PERFIL_OPCOES, key="d_perfil")
    faixa = c4.selectbox("Distância da perícia", ZONA_PCI_OPCOES, key="d_faixa")

    view = _aplicar_filtros(df, busca, porte, perfil, faixa)

    # -------------------------------------------------------------------------
    # Resumo do subconjunto
    # -------------------------------------------------------------------------
    pop = int(view["populacao_censo_2022"].sum()) if not view.empty else 0
    total = int(view["valor_total"].sum()) if not view.empty else 0
    anos = max(filtros.semestres_no_recorte, 1) / 2.0
    taxa = (total / pop / anos * filtros.fator_pop) if pop else None

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Municípios", f"{len(view)} de {len(df)}")
    m2.metric("População coberta", f"{formatar_numero(pop)} hab.")
    m3.metric(unidade.capitalize(), formatar_numero(total))
    m4.metric(f"Taxa anual {filtros.rotulo_escala}", formatar_taxa(taxa))

    if view.empty:
        st.info("Nenhum município atende aos filtros escolhidos.")
        return

    # -------------------------------------------------------------------------
    # Ordenacao
    # -------------------------------------------------------------------------
    opcoes_ordem = {
        f"Taxa anual {filtros.rotulo_escala}": "taxa_exibicao",
        f"Total ({unidade})": "valor_total",
        "Indício penal": "valor_penal",
        "Demanda socioassistencial": "valor_social",
        "Percentual penal": "pct_penal",
        "População (Censo 2022)": "populacao_censo_2022",
        "Distância da perícia": "distancia_pci_km",
        "Nome do município": "municipio",
    }
    col_o1, col_o2 = st.columns([7, 3])
    escolha = col_o1.selectbox("Ordenar por", list(opcoes_ordem.keys()), key="d_ordem")
    coluna_ordem = opcoes_ordem[escolha]

    if coluna_ordem == "municipio":
        direcao = col_o2.radio("Direção", ["A a Z", "Z a A"], horizontal=True, key="d_dir_txt")
        crescente = direcao == "A a Z"
    else:
        direcao = col_o2.radio(
            "Direção", ["Maior primeiro", "Menor primeiro"], horizontal=True, key="d_dir_num"
        )
        crescente = direcao == "Menor primeiro"

    ordenado = view.sort_values(coluna_ordem, ascending=crescente, na_position="last").reset_index(drop=True)
    ordenado.insert(0, "posicao", range(1, len(ordenado) + 1))

    # -------------------------------------------------------------------------
    # Tabela
    # -------------------------------------------------------------------------
    tabela = pd.DataFrame({
        "#": ordenado["posicao"],
        "Município": ordenado["municipio"],
        "Região intermediária": ordenado["regiao_intermediaria"],
        "População": ordenado["populacao_censo_2022"].map(formatar_numero),
        "Total": ordenado["valor_total"].map(formatar_numero),
        "Indício penal": ordenado["valor_penal"].map(formatar_numero),
        "Demanda social": ordenado["valor_social"].map(formatar_numero),
        "% penal": ordenado["pct_penal"].map(formatar_percentual),
        "Taxa total": ordenado["taxa_total"].map(formatar_taxa),
        "Taxa penal": ordenado["taxa_penal"].map(formatar_taxa),
        "Distância da PCI": ordenado["distancia_pci_km"].map(formatar_km),
        "Unidade pericial": ordenado["pci_proxima_municipio"].fillna(SEM_DADO)
        if "pci_proxima_municipio" in ordenado.columns else SEM_DADO,
    })
    st.dataframe(tabela, hide_index=True, width="stretch", height=430)

    if coluna_ordem in ("taxa_exibicao", "pct_penal") and not crescente:
        st.caption(
            "Ordenar por taxa coloca no topo municípios muito pequenos, cuja taxa oscila em "
            "ordens de magnitude a cada denúncia. A tabela mostra todos os municípios de "
            "propósito; o piso populacional da barra lateral vale para os rankings e o mapa, "
            "onde a leitura é comparativa."
        )

    with st.expander("Dicionário de colunas"):
        st.dataframe(
            pd.DataFrame(
                {"Coluna": list(DICIONARIO_COLUNAS.keys()), "Significado": list(DICIONARIO_COLUNAS.values())}
            ),
            hide_index=True,
            width="stretch",
        )

    # -------------------------------------------------------------------------
    # Exportacao
    # -------------------------------------------------------------------------
    base_nome = f"sc_disque100_{filtros.grupo}_{filtros.year_param}_{filtros.unidade_efetiva()}"
    exportavel = _preparar_exportacao(ordenado)

    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "Baixar CSV",
        data=exportavel.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{base_nome}.csv",
        mime="text/csv",
        width="stretch",
    )
    d2.download_button(
        "Baixar JSON",
        data=exportavel.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8"),
        file_name=f"{base_nome}.json",
        mime="application/json",
        width="stretch",
    )
    buffer = io.BytesIO()
    exportavel.to_parquet(buffer, index=False)
    d3.download_button(
        "Baixar Parquet",
        data=buffer.getvalue(),
        file_name=f"{base_nome}.parquet",
        mime="application/octet-stream",
        width="stretch",
    )
    st.caption(
        "A exportação traz os valores numéricos sem formatação, na unidade de medida e no "
        "recorte ativos, com a coluna de unidade registrada para rastreabilidade."
    )


def _aplicar_filtros(
    df: pd.DataFrame, busca: str, porte: str, perfil: str, faixa: str
) -> pd.DataFrame:
    view = df

    if porte == PORTE_OPCOES[1]:
        view = view[view["populacao_censo_2022"] < 20_000]
    elif porte == PORTE_OPCOES[2]:
        view = view[(view["populacao_censo_2022"] >= 20_000) & (view["populacao_censo_2022"] < 50_000)]
    elif porte == PORTE_OPCOES[3]:
        view = view[(view["populacao_censo_2022"] >= 50_000) & (view["populacao_censo_2022"] < 100_000)]
    elif porte == PORTE_OPCOES[4]:
        view = view[view["populacao_censo_2022"] >= 100_000]

    if perfil == PERFIL_OPCOES[1]:
        view = view[view["pct_penal"] >= 60.0]
    elif perfil == PERFIL_OPCOES[2]:
        view = view[view["pct_penal"] <= 40.0]
    elif perfil == PERFIL_OPCOES[3]:
        # A media de comparacao usa a mesma metrica exibida, e nao o total:
        # comparar a taxa penal contra a media do total classificava errado.
        pop = view["populacao_censo_2022"].sum()
        media = (view["valor_exibicao"].sum() / pop) if pop else None
        if media:
            per_capita = view["valor_exibicao"] / view["populacao_censo_2022"].where(
                view["populacao_censo_2022"] > 0
            )
            view = view[per_capita >= media]

    if faixa == FAIXA_PROXIMA:
        view = view[view["faixa_distancia"] == FAIXA_PROXIMA]
    elif faixa == FAIXA_INTERMEDIARIA:
        view = view[view["faixa_distancia"] == FAIXA_INTERMEDIARIA]
    elif faixa == FAIXA_DISTANTE:
        view = view[view["faixa_distancia"] == FAIXA_DISTANTE]

    if busca:
        termo = busca.strip().lower()
        colunas_texto = ["municipio", "regiao_intermediaria", "regiao_imediata", "ibge_code"]
        mascara = False
        for coluna in colunas_texto:
            if coluna in view.columns:
                mascara = mascara | view[coluna].astype(str).str.lower().str.contains(termo, na=False)
        view = view[mascara]

    return view


def _preparar_exportacao(df: pd.DataFrame) -> pd.DataFrame:
    colunas = [
        "ibge_code", "municipio", "regiao_intermediaria", "regiao_imediata",
        "populacao_censo_2022", "valor_total", "valor_penal", "valor_social",
        "pct_penal", "taxa_total", "taxa_penal", "taxa_social",
        "distancia_pci_km", "faixa_distancia", "pci_proxima",
    ]
    presentes = [c for c in colunas if c in df.columns]
    return df[presentes].copy()
