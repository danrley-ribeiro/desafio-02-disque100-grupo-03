"""
=============================================================================
Aba Territorio: mapa coropletico, rankings e evolucao no tempo
=============================================================================
O mapa e um coropletico Plotly construido sobre a malha municipal do IBGE
versionada em data/processed/. Ele responde a todos os filtros.

Antes, a aba embutia um HTML Folium de 1,1 MB cujo JavaScript ignorava os
filtros de ano e de regiao: selecionar 2015 atualizava os cartoes e as tabelas,
e o mapa continuava mostrando o periodo inteiro. Esse mapa permanece
disponivel, em um bloco recolhido, rotulado com o periodo que de fato exibe.

O ranking aparece em duas leituras lado a lado, porque elas respondem a
perguntas diferentes: volume absoluto indica onde esta a carga de trabalho;
taxa por habitante indica onde a incidencia e proporcionalmente maior. A taxa
respeita o piso populacional, sem o qual o topo do ranking e ocupado por
municipios de poucos milhares de habitantes cuja taxa oscila em ordens de
magnitude a cada denuncia.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from streamlit_app.config import (
    AJUDA_FOCOS,
    AJUDA_PCI_MAPA,
    AJUDA_POP_MINIMA,
    AJUDA_RODOVIAS,
    CATEGORICA,
    COR_PENAL,
    COR_SOCIAL,
    Filtros,
    NATUREZA_ROTULO,
    UNIDADE_ROTULO,
)
from streamlit_app.utils.charts import (
    ALTURA_PADRAO,
    barras_horizontais,
    camada_focos,
    camada_rodovias,
    camada_unidades_periciais,
    coropleto,
    series_temporal,
)
from streamlit_app.utils.formatters import formatar_numero, formatar_taxa

TOPO = 12


def render_tab_territorio(
    df: pd.DataFrame,
    df_ano: pd.DataFrame,
    filtros: Filtros,
    malha: Optional[Dict[str, Any]],
    html_folium: Optional[str],
    eixos: Optional[List[Dict[str, Any]]] = None,
    df_pci: Optional[pd.DataFrame] = None,
) -> None:
    if df.empty:
        st.info("Nenhum município no recorte selecionado.")
        return

    unidade = UNIDADE_ROTULO[filtros.unidade_efetiva()]
    natureza = NATUREZA_ROTULO[filtros.natureza]
    rotulo_valor = f"{natureza} ({unidade})"
    rotulo_taxa = f"Taxa anual {filtros.rotulo_escala}"

    # -------------------------------------------------------------------------
    # Mapa
    # -------------------------------------------------------------------------
    st.subheader("Distribuição territorial")
    aba_taxa, aba_volume = st.tabs([rotulo_taxa, "Volume absoluto"])

    if malha:
        with aba_taxa:
            _render_mapa(df, malha, "taxa_exibicao", rotulo_taxa, filtros, eixos, df_pci, True)
        with aba_volume:
            _render_mapa(df, malha, "valor_exibicao", rotulo_valor, filtros, eixos, df_pci, False)
    else:
        with aba_taxa:
            st.warning(
                "Malha municipal não encontrada. Execute `python3 scripts/gerar_geo_pci_sc.py` "
                "para gerar `data/processed/sc_malha_municipios.geojson`."
            )

    # -------------------------------------------------------------------------
    # Rankings
    # -------------------------------------------------------------------------
    st.subheader("Municípios em destaque")
    col_vol, col_taxa = st.columns(2)

    with col_vol:
        st.markdown(f"**Maior volume** — {natureza}")
        st.caption(f"Contagem de {unidade} no período e território selecionados.")
        topo_vol = df.nlargest(TOPO, "valor_exibicao")
        st.plotly_chart(
            barras_horizontais(
                topo_vol,
                coluna_categoria="municipio",
                coluna_valor="valor_exibicao",
                rotulo_valor=unidade.capitalize(),
                cor=CATEGORICA[0],
                colunas_extra={"populacao_censo_2022": "População"},
                altura=ALTURA_PADRAO,
            ),
            width="stretch",
            key="ranking_volume",
        )

    with col_taxa:
        st.markdown(f"**Maior taxa por habitante** — {natureza}")
        elegiveis = df[df["populacao_censo_2022"] >= filtros.pop_minima]
        if filtros.pop_minima > 0:
            excluidos = len(df) - len(elegiveis)
            st.caption(
                f"Piso de {formatar_numero(filtros.pop_minima)} habitantes: "
                f"{excluidos} de {len(df)} municípios fora do ranking por taxa."
            )
        else:
            st.caption(
                "Sem piso populacional. Municípios de poucos milhares de habitantes "
                "dominam o topo com taxas instáveis."
            )

        if elegiveis.empty:
            st.info("Nenhum município atinge o piso populacional escolhido.")
        else:
            topo_taxa = elegiveis.nlargest(TOPO, "taxa_exibicao")
            st.plotly_chart(
                barras_horizontais(
                    topo_taxa,
                    coluna_categoria="municipio",
                    coluna_valor="taxa_exibicao",
                    rotulo_valor=rotulo_taxa,
                    cor=CATEGORICA[2],
                    colunas_extra={
                        "populacao_censo_2022": "População",
                        "valor_exibicao": unidade.capitalize(),
                    },
                    altura=ALTURA_PADRAO,
                ),
                width="stretch",
                key="ranking_taxa",
            )

    media = _taxa_media(df, filtros)
    if media and not elegiveis.empty:
        maior = elegiveis.nlargest(1, "taxa_exibicao").iloc[0]
        razao = maior["taxa_exibicao"] / media if media else None
        if razao and pd.notna(razao):
            st.caption(
                f"Média do recorte: {formatar_taxa(media)} {filtros.rotulo_escala} "
                f"O maior valor entre os municípios acima do piso é "
                f"{maior['municipio']}, com {formatar_taxa(maior['taxa_exibicao'])}: "
                f"{formatar_taxa(razao)} vezes a média."
            )

    # -------------------------------------------------------------------------
    # Evolucao no tempo
    # -------------------------------------------------------------------------
    _render_serie(df_ano, filtros)

    # -------------------------------------------------------------------------
    # Mapa Folium pre-gerado
    # -------------------------------------------------------------------------
    with st.expander("Mapa detalhado pré-gerado (período completo, não segue os filtros)"):
        st.caption(
            "Mapa Folium gerado fora do painel, com agrupamentos, rodovias e as unidades "
            "periciais. Exibe sempre o acumulado de todo o período, independentemente do "
            "recorte escolhido na barra lateral."
        )
        if html_folium:
            _embutir_html(_injetar_config(html_folium, filtros), altura=640)
        else:
            st.warning(
                "Arquivo não encontrado. Execute "
                "`python3 scripts/generate_sc_disque100_folium_dashboard.py`."
            )


def _embutir_html(html: str, *, altura: int) -> None:
    """
    Embute o HTML do mapa pré-gerado.

    `st.components.v1.html` está depreciado e será removido; `st.iframe` é o
    substituto, mas só existe a partir do Streamlit 1.49. A escolha é feita em
    tempo de execução para que o painel funcione em ambas as versões.
    """
    if hasattr(st, "iframe"):
        st.iframe(html, height=altura, width="stretch")
    else:
        components.html(html, height=altura, scrolling=False)


def _render_mapa(
    df: pd.DataFrame,
    malha: Dict[str, Any],
    coluna: str,
    rotulo: str,
    filtros: Filtros,
    eixos: Optional[List[Dict[str, Any]]],
    df_pci: Optional[pd.DataFrame],
    aplicar_piso_nos_focos: bool,
) -> None:
    dados = df.dropna(subset=[coluna])
    if dados.empty:
        st.info("Sem valores para exibir no mapa neste recorte.")
        return

    fig = coropleto(
        dados,
        malha,
        coluna_id="ibge_code",
        coluna_valor=coluna,
        rotulo_valor=rotulo,
        colunas_extra={
            "populacao_censo_2022": "População",
            "regiao_intermediaria": "Região intermediária",
        },
    )

    if filtros.camada_rodovias and eixos:
        camada_rodovias(fig, eixos)
    if filtros.camada_pci and df_pci is not None:
        camada_unidades_periciais(fig, df_pci)
    if filtros.camada_focos and "lat" in dados.columns:
        elegiveis = (
            dados[dados["populacao_censo_2022"] >= filtros.pop_minima]
            if aplicar_piso_nos_focos else dados
        )
        focos = elegiveis.nlargest(min(filtros.quantidade_focos, len(elegiveis)), coluna)
        camada_focos(fig, focos, coluna_valor=coluna, rotulo_valor=rotulo)

    st.plotly_chart(fig, width="stretch", key=f"mapa_{coluna}")

    partes = [
        f"{len(dados)} municípios",
        filtros.label_periodo,
        filtros.rotulo_territorio,
        filtros.rotulo_grupo.lower(),
    ]
    st.caption(" · ".join(partes))

    notas = []
    if filtros.camada_rodovias and eixos:
        notas.append(f"Eixos rodoviários: {AJUDA_RODOVIAS}")
    if filtros.camada_pci and df_pci is not None and not df_pci.empty:
        notas.append(f"Unidades periciais: {AJUDA_PCI_MAPA}")
    if filtros.camada_focos:
        piso = (
            f" Piso de {formatar_numero(filtros.pop_minima)} habitantes aplicado."
            if (aplicar_piso_nos_focos and filtros.pop_minima) else ""
        )
        notas.append(f"Pontos de foco: {AJUDA_FOCOS}{piso}")
    if notas:
        with st.expander("Sobre as camadas do mapa"):
            for n in notas:
                st.markdown(f"- {n}")


def _taxa_media(df: pd.DataFrame, filtros: Filtros) -> Optional[float]:
    """Taxa do recorte como um todo, e nao media das taxas municipais."""
    pop = df["populacao_censo_2022"].sum()
    if not pop:
        return None
    anos = max(filtros.semestres_no_recorte, 1) / 2.0
    return (df["valor_exibicao"].sum() / pop / anos) * filtros.fator_pop


def _render_serie(df_ano: pd.DataFrame, filtros: Filtros) -> None:
    """Serie anual de penal e socioassistencial no territorio selecionado."""
    if df_ano.empty or "ano" not in df_ano.columns:
        return

    sub = df_ano
    if filtros.regioes:
        sub = sub[sub["regiao_intermediaria"].isin(filtros.regioes)]
    if sub.empty:
        return

    coluna_total, coluna_penal = filtros.colunas()
    if coluna_total not in sub.columns:
        return

    serie = (
        sub.groupby("ano", as_index=False)
        .agg(total=(coluna_total, "sum"), penal=(coluna_penal, "sum"), semestres=("semestre", "nunique"))
    )
    serie["social"] = serie["total"] - serie["penal"]
    serie["ano"] = serie["ano"].astype(int)

    unidade = UNIDADE_ROTULO[filtros.unidade_efetiva()]
    st.subheader("Evolução anual")

    # Anos com um semestre so nao sao comparaveis aos demais em valor absoluto.
    parciais = serie[(serie["semestres"] == 1) & (serie["ano"] >= 2020)]["ano"].tolist()
    if parciais:
        st.caption(
            "Contagem de "
            + unidade
            + " por ano no território selecionado. "
            + ", ".join(str(a) for a in parciais)
            + " tem apenas um semestre de dados e aparece abaixo do patamar real."
        )
    else:
        st.caption(f"Contagem de {unidade} por ano no território selecionado.")

    st.plotly_chart(
        series_temporal(
            serie,
            coluna_x="ano",
            series=[
                ("penal", "Indício de infração penal", COR_PENAL),
                ("social", "Demanda socioassistencial", COR_SOCIAL),
            ],
            rotulo_valor=unidade.capitalize(),
            titulo_x="Ano",
            marcar_parcial=min(parciais) if parciais else None,
        ),
        width="stretch",
        key="serie_territorio",
    )


def _injetar_config(html: str, filtros: Filtros) -> str:
    """
    Injeta o estado dos filtros no HTML do mapa pre-gerado, uma unica vez.

    A versao anterior injetava o mesmo bloco no `<head>` e antes de `</body>`,
    deixando duas atribuicoes e dois temporizadores de 20 Hz ativos, o do
    `<head>` sem condicao de parada.
    """
    from streamlit_app.components.sidebar import topico_folium

    script = f"""
    <script>
      window.ACTIVE_STREAMLIT_CONFIG = {{
        topic: "{topico_folium(filtros)}",
        metricType: "{filtros.natureza}",
        scale: {filtros.fator_pop},
        region: "{filtros.region_code}",
        year: "all",
        showClusters: {str(filtros.camada_clusters).lower()},
        showPCI: {str(filtros.camada_pci).lower()},
        showRoads: {str(filtros.camada_rodovias).lower()},
        showPeaks: true
      }};
      (function aplicar(tentativas) {{
        if (typeof window.applyActiveFilters === 'function') {{
          window.applyActiveFilters(window.ACTIVE_STREAMLIT_CONFIG);
        }} else if (tentativas > 0) {{
          setTimeout(function () {{ aplicar(tentativas - 1); }}, 50);
        }}
      }})(100);
    </script>
    """
    if "</body>" in html:
        return html.replace("</body>", f"{script}\n</body>", 1)
    return html + script
