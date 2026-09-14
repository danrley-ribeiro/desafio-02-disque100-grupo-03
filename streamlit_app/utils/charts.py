"""
=============================================================================
Tema e construtores de graficos do painel
=============================================================================
Um unico tema aplicado a todas as figuras, para que o painel leia como um
sistema. Antes havia tres `st.bar_chart` sem eixo rotulado, sem dica de
contexto e sem formatacao numerica brasileira, embora o projeto ja declarasse
Plotly como dependencia.

Regras seguidas em todas as figuras:
  - uma unica escala de valor por figura, nunca dois eixos;
  - matizes categoricas em ordem fixa, atribuidas a entidade e nao ao posto,
    de modo que filtrar series nao repinta as sobreviventes;
  - magnitude continua em rampa de matiz unico, do claro ao escuro;
  - grade e eixos discretos, marcas finas, sem rotulo em cada ponto;
  - legenda presente a partir de duas series e ausente com uma so, ja que o
    titulo nomeia a serie;
  - numeros em formato brasileiro na dica de contexto e nos eixos.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import pandas as pd
import plotly.graph_objects as go

from streamlit_app.config import (
    CATEGORICA,
    COR_FOCO,
    COR_PCI,
    COR_RODOVIA,
    FONTE,
    GRADE,
    LINHA_BASE,
    SEQUENCIAL_AZUL,
    TINTA_DISCRETA,
    TINTA_PRIMARIA,
    TINTA_SECUNDARIA,
)

# Separador de milhar brasileiro nos eixos e nas dicas de contexto.
SEPARADORES_BR = {"thousands": ".", "decimal": ","}

# Altura padrao das figuras, em pixels.
ALTURA_PADRAO = 380
ALTURA_BAIXA = 300


def aplicar_tema(
    fig: go.Figure,
    *,
    altura: int = ALTURA_PADRAO,
    titulo_x: str = "",
    titulo_y: str = "",
    mostrar_legenda: Optional[bool] = None,
    grade_x: bool = False,
    grade_y: bool = True,
) -> go.Figure:
    """
    Aplica o tema do painel a uma figura ja montada.

    `mostrar_legenda` em None decide pela contagem de series: a partir de duas
    a legenda aparece, com uma so ela e redundante com o titulo.
    """
    if mostrar_legenda is None:
        mostrar_legenda = len([t for t in fig.data if t.showlegend is not False]) >= 2

    fig.update_layout(
        height=altura,
        margin=dict(l=8, r=8, t=8, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONTE, size=12, color=TINTA_SECUNDARIA),
        separators=".,",
        showlegend=mostrar_legenda,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=11, color=TINTA_SECUNDARIA),
            title_text="",
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor=LINHA_BASE,
            font=dict(family=FONTE, size=12, color=TINTA_PRIMARIA),
        ),
        bargap=0.28,
        bargroupgap=0.06,
    )
    fig.update_xaxes(
        title_text=titulo_x,
        title_font=dict(size=11, color=TINTA_DISCRETA),
        tickfont=dict(size=11, color=TINTA_DISCRETA),
        showgrid=grade_x,
        gridcolor=GRADE,
        gridwidth=1,
        zeroline=False,
        linecolor=LINHA_BASE,
        showline=True,
        ticks="outside",
        ticklen=4,
        tickcolor=LINHA_BASE,
    )
    fig.update_yaxes(
        title_text=titulo_y,
        title_font=dict(size=11, color=TINTA_DISCRETA),
        tickfont=dict(size=11, color=TINTA_DISCRETA),
        showgrid=grade_y,
        gridcolor=GRADE,
        gridwidth=1,
        zeroline=False,
        linecolor=LINHA_BASE,
        showline=False,
        ticks="",
    )
    return fig


def barras_horizontais(
    df: pd.DataFrame,
    *,
    coluna_categoria: str,
    coluna_valor: str,
    rotulo_valor: str,
    cor: str = CATEGORICA[0],
    sufixo_dica: str = "",
    colunas_extra: Optional[Dict[str, str]] = None,
    altura: int = ALTURA_PADRAO,
) -> go.Figure:
    """
    Ranking em barras horizontais, maior no topo.

    Barra horizontal e a forma certa para comparar magnitude entre entidades
    nomeadas: o rotulo cabe na horizontal, sem texto girado.
    """
    dados = df.sort_values(coluna_valor, ascending=True)
    extras = colunas_extra or {}

    linhas_dica = [f"<b>%{{y}}</b>", f"{rotulo_valor}: %{{x:,.1f}}{sufixo_dica}"]
    customdata: Optional[Any] = None
    if extras:
        customdata = dados[list(extras.keys())].to_numpy()
        for i, rotulo in enumerate(extras.values()):
            linhas_dica.append(f"{rotulo}: %{{customdata[{i}]}}")

    fig = go.Figure(
        go.Bar(
            x=dados[coluna_valor],
            y=dados[coluna_categoria],
            orientation="h",
            marker=dict(color=cor, cornerradius=4),
            customdata=customdata,
            hovertemplate="<br>".join(linhas_dica) + "<extra></extra>",
            showlegend=False,
        )
    )
    return aplicar_tema(fig, altura=altura, titulo_x=rotulo_valor, grade_x=True, grade_y=False)


def barras_empilhadas(
    df: pd.DataFrame,
    *,
    coluna_categoria: str,
    series: Sequence[tuple],
    rotulo_valor: str,
    horizontal: bool = True,
    altura: int = ALTURA_PADRAO,
) -> go.Figure:
    """
    Composicao de duas ou mais partes de um total.

    `series` e uma sequencia de (coluna, rotulo, cor). O vao de 2 pixels entre
    segmentos evita que duas partes adjacentes se leiam como uma so.
    """
    fig = go.Figure()
    for coluna, rotulo, cor in series:
        eixo = dict(y=df[coluna_categoria], x=df[coluna]) if horizontal else dict(
            x=df[coluna_categoria], y=df[coluna]
        )
        fig.add_trace(
            go.Bar(
                name=rotulo,
                orientation="h" if horizontal else "v",
                marker=dict(color=cor, line=dict(color="#fcfcfb", width=2), cornerradius=3),
                hovertemplate=f"<b>%{{{'y' if horizontal else 'x'}}}</b><br>{rotulo}: "
                              f"%{{{'x' if horizontal else 'y'}:,.0f}}<extra></extra>",
                **eixo,
            )
        )
    fig.update_layout(barmode="stack")
    return aplicar_tema(
        fig,
        altura=altura,
        titulo_x=rotulo_valor if horizontal else "",
        titulo_y="" if horizontal else rotulo_valor,
        grade_x=horizontal,
        grade_y=not horizontal,
    )


def series_temporal(
    df: pd.DataFrame,
    *,
    coluna_x: str,
    series: Sequence[tuple],
    rotulo_valor: str,
    titulo_x: str = "",
    marcar_parcial: Optional[Any] = None,
    altura: int = ALTURA_PADRAO,
) -> go.Figure:
    """
    Evolucao no tempo em linhas de 2 pixels com marcadores de 8 pixels.

    `marcar_parcial` recebe o valor de x cujo periodo esta incompleto; o ponto
    e desenhado com traco pontilhado e anotado, para que uma cobertura parcial
    nao seja lida como queda de demanda.
    """
    fig = go.Figure()
    for coluna, rotulo, cor in series:
        fig.add_trace(
            go.Scatter(
                x=df[coluna_x],
                y=df[coluna],
                name=rotulo,
                mode="lines+markers",
                line=dict(color=cor, width=2),
                marker=dict(color=cor, size=8, line=dict(color="#fcfcfb", width=2)),
                hovertemplate=f"<b>%{{x}}</b><br>{rotulo}: %{{y:,.0f}}<extra></extra>",
            )
        )

    fig.update_layout(hovermode="x unified")
    fig = aplicar_tema(fig, altura=altura, titulo_x=titulo_x, titulo_y=rotulo_valor)

    if marcar_parcial is not None and len(df):
        fig.add_vline(
            x=marcar_parcial,
            line=dict(color=TINTA_DISCRETA, width=1, dash="dot"),
        )
        fig.add_annotation(
            x=marcar_parcial,
            yref="paper",
            y=1.0,
            text="cobertura parcial",
            showarrow=False,
            font=dict(size=10, color=TINTA_DISCRETA),
            xanchor="right",
            yanchor="bottom",
        )
    return fig


def coropleto(
    df: pd.DataFrame,
    geojson: Dict[str, Any],
    *,
    coluna_id: str,
    coluna_valor: str,
    rotulo_valor: str,
    colunas_extra: Optional[Dict[str, str]] = None,
    altura: int = 520,
) -> go.Figure:
    """
    Mapa coropletico municipal em rampa sequencial de matiz unico.

    A chave `codarea` da malha do IBGE e o proprio codigo de municipio de sete
    digitos, portanto a juncao e direta.
    """
    extras = colunas_extra or {}
    linhas_dica = [f"<b>%{{customdata[0]}}</b>", f"{rotulo_valor}: %{{z:,.1f}}"]
    colunas_custom = [c for c in extras.keys()]
    for i, rotulo in enumerate(extras.values(), start=1):
        linhas_dica.append(f"{rotulo}: %{{customdata[{i}]}}")

    fig = go.Figure(
        go.Choropleth(
            geojson=geojson,
            featureidkey="properties.codarea",
            locations=df[coluna_id],
            z=df[coluna_valor],
            customdata=df[["municipio"] + colunas_custom].to_numpy(),
            colorscale=[[i / (len(SEQUENCIAL_AZUL) - 1), c] for i, c in enumerate(SEQUENCIAL_AZUL)],
            marker=dict(line=dict(color="#334155", width=0.4)),
            hovertemplate="<br>".join(linhas_dica) + "<extra></extra>",
            colorbar=dict(
                title=dict(text=rotulo_valor, side="right", font=dict(size=11, color=TINTA_DISCRETA)),
                thickness=12,
                len=0.85,
                tickfont=dict(size=10, color=TINTA_DISCRETA),
                outlinewidth=0,
            ),
        )
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=0,
            xanchor="left",
            x=0,
            bgcolor="rgba(252,252,251,0.85)",
            bordercolor=LINHA_BASE,
            borderwidth=1,
            font=dict(size=10, color=TINTA_SECUNDARIA),
            title_text="",
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONTE, size=12, color=TINTA_SECUNDARIA),
        separators=".,",
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor=LINHA_BASE,
            font=dict(family=FONTE, size=12, color=TINTA_PRIMARIA),
        ),
    )
    return fig


def camada_rodovias(fig: go.Figure, eixos: Sequence[Dict[str, Any]]) -> go.Figure:
    """
    Sobrepoe os eixos rodoviarios de referencia ao mapa.

    Todos os eixos usam a mesma tinta neutra, com a federal mais espessa que a
    estadual: a cor esta reservada a escala de valor dos municipios. O mapa
    Folium anterior dava uma matiz diferente a cada uma das vinte rodovias, o
    que competia com o dado.
    """
    for grupo, largura, tracado in (("federal", 2.0, "solid"), ("estadual", 1.2, "solid")):
        do_grupo = [e for e in eixos if e.get("tipo") == grupo]
        for i, eixo in enumerate(do_grupo):
            coords = eixo.get("coords") or []
            if not coords:
                continue
            fig.add_trace(
                go.Scattergeo(
                    lat=[c[0] for c in coords],
                    lon=[c[1] for c in coords],
                    mode="lines",
                    line=dict(color=COR_RODOVIA, width=largura, dash=tracado),
                    opacity=0.55,
                    name="Rodovias federais" if grupo == "federal" else "Rodovias estaduais",
                    legendgroup=grupo,
                    showlegend=(i == 0),
                    hovertemplate=f"<b>{eixo.get('nome', '')}</b><br>{eixo.get('descricao', '')}"
                                  "<extra></extra>",
                )
            )
    return fig


def camada_unidades_periciais(fig: go.Figure, df_pci: pd.DataFrame) -> go.Figure:
    """Sobrepoe as unidades da Policia Cientifica, por tipo de unidade."""
    if df_pci.empty or "lat" not in df_pci.columns:
        return fig
    validas = df_pci[(df_pci["lat"].notna()) & (df_pci["lat"] != 0)]
    if validas.empty:
        return fig

    for tipo, simbolo, tamanho in (
        ("Superintendência Regional", "square", 11),
        ("Núcleo Regional", "diamond", 8),
    ):
        do_tipo = validas[validas["tipo"] == tipo] if "tipo" in validas.columns else validas
        if do_tipo.empty:
            continue
        fig.add_trace(
            go.Scattergeo(
                lat=do_tipo["lat"],
                lon=do_tipo["lon"],
                mode="markers",
                marker=dict(
                    color=COR_PCI,
                    size=tamanho,
                    symbol=simbolo,
                    line=dict(color="#fcfcfb", width=1.4),
                ),
                name=tipo,
                customdata=do_tipo[["municipio", "sigla"]].to_numpy()
                if "sigla" in do_tipo.columns else do_tipo[["municipio", "municipio"]].to_numpy(),
                hovertemplate="<b>%{customdata[0]}</b><br>" + tipo
                              + "<br>%{customdata[1]}<extra></extra>",
            )
        )
    return fig


def camada_focos(
    fig: go.Figure,
    df_focos: pd.DataFrame,
    *,
    coluna_valor: str,
    rotulo_valor: str,
) -> go.Figure:
    """
    Sobrepoe os municipios de maior incidencia como pontos de foco.

    O anel e vazado para que a cor do municipio abaixo continue legivel: o
    ponto marca onde esta o foco, a escala de cor continua carregando o valor.
    """
    if df_focos.empty or "lat" not in df_focos.columns:
        return fig
    validas = df_focos[df_focos["lat"].notna()]
    if validas.empty:
        return fig

    fig.add_trace(
        go.Scattergeo(
            lat=validas["lat"],
            lon=validas["lng"],
            mode="markers",
            marker=dict(
                color="rgba(0,0,0,0)",
                size=17,
                symbol="circle",
                line=dict(color=COR_FOCO, width=3),
            ),
            name=f"Focos: {len(validas)} municípios de maior incidência",
            customdata=validas[["municipio", coluna_valor]].to_numpy(),
            hovertemplate="<b>%{customdata[0]}</b><br>" + rotulo_valor
                          + ": %{customdata[1]:,.1f}<extra></extra>",
        )
    )
    return fig


def cores_para(chaves: Sequence[str]) -> Dict[str, str]:
    """
    Associa cada chave a uma matiz categorica em ordem fixa.

    A associacao e por entidade, nao por posto: a mesma chave recebe a mesma cor
    independentemente de quantas series o filtro deixou na tela.
    """
    return {chave: CATEGORICA[i % len(CATEGORICA)] for i, chave in enumerate(chaves)}
