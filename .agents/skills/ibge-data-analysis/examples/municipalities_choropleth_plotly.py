#!/usr/bin/env python3
"""
=============================================================================
Exemplo Prático: Mapa dos 295 Municípios de Santa Catarina (Plotly)
=============================================================================
Gera um mapa interativo coroplético perfeitamente enquadrado para todos
os 295 municípios de Santa Catarina, com contraste aprimorado e bordas
nítidas para garantir visibilidade total em qualquer valor.
=============================================================================
"""

import sys
import pandas as pd
import plotly.express as px
from pathlib import Path

# Adiciona diretório de scripts para importar o client
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from ibge_client import IBGEClient

def main():
    client = IBGEClient()
    uf_alvo = "SC"

    print(f"1. Baixando malha vetorial dos 295 municípios de Santa Catarina ({uf_alvo})...")
    geojson_sc = client.get_malha_municipios_uf_geojson(uf=uf_alvo, qualidade="minima")

    print(f"2. Obtendo metadados oficiais dos municípios de Santa Catarina...")
    df_loc = client.get_municipios_df(uf=uf_alvo, engine="pandas")

    print("3. Preparando indicadores dos 295 municípios catarinenses...")
    df_dados = pd.DataFrame({
        "codarea": df_loc["municipio-id"].astype(str),
        "municipio": df_loc["municipio-nome"],
        "regiao_imediata": df_loc["regiao-imediata-nome"],
        "regiao_intermediaria": df_loc["regiao-intermediaria-nome"],
        "taxa_atendimento": [65 + (i * 11 % 33) for i in range(len(df_loc))]
    })

    # Escala de cores de alto contraste (inicia em azul celeste bem visível, nunca branco)
    custom_blues = [
        [0.0, "#93c5fd"],  # Azul celeste claro visível
        [0.3, "#60a5fa"],
        [0.6, "#2563eb"],
        [1.0, "#1e3a8a"]   # Azul marinho
    ]

    print("4. Construindo mapa coroplético...")
    fig = px.choropleth(
        df_dados,
        geojson=geojson_sc,
        locations="codarea",
        featureidkey="properties.codarea",
        color="taxa_atendimento",
        color_continuous_scale=custom_blues,
        hover_name="municipio",
        hover_data={
            "regiao_intermediaria": True,
            "regiao_imediata": True,
            "taxa_atendimento": ":.1f",
            "codarea": False
        },
        title="<b>Municípios de Santa Catarina</b><br><sup>Total: 295 Municípios | Fonte: IBGE</sup>",
        labels={"taxa_atendimento": "Taxa (%)"}
    )

    fig.update_geos(
        fitbounds="locations",
        visible=False
    )

    # Bordas em tom slate-700 para contraste e delimitação nítida de cada cidade
    fig.update_traces(
        marker_line_width=0.7,
        marker_line_color="#334155"
    )

    fig.update_layout(
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        autosize=True
    )

    output_html = "mapa_sc_municipios_plotly.html"
    fig.write_html(output_html, include_plotlyjs=True)
    print(f"✅ Mapa dos 295 municípios de SC salvo com sucesso em '{output_html}'!")

if __name__ == "__main__":
    main()
