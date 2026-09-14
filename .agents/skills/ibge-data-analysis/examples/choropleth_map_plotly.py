#!/usr/bin/env python3
"""
=============================================================================
Exemplo Prático: Regiões Intermediárias de Santa Catarina (Plotly)
=============================================================================
Gera um mapa coroplético para TODAS as 7 Regiões Intermediárias de Santa Catarina
(Florianópolis, Blumenau, Joinville, Chapecó, Criciúma, Lages e Caçador)
usando a malha oficial do IBGE e sem nenhuma região vazia.
=============================================================================
"""

import sys
import pandas as pd
import plotly.express as px
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from ibge_client import IBGEClient

def main():
    client = IBGEClient()
    uf_alvo = "SC"
    
    print(f"1. Baixando malha das Regiões Intermediárias de Santa Catarina ({uf_alvo})...")
    geojson_intermed = client.get_malha_municipios_uf_geojson(
        uf=uf_alvo,
        intrarregiao="regiao-intermediaria",
        qualidade="minima"
    )

    print("2. Obtendo as 7 Regiões Intermediárias oficiais do IBGE...")
    # Todas as 7 regiões intermediárias oficiais de Santa Catarina
    dados_sc = [
        {"codarea": "4201", "nome_regiao": "Florianópolis", "total_demandas": 19876},
        {"codarea": "4202", "nome_regiao": "Criciúma", "total_demandas": 12559},
        {"codarea": "4203", "nome_regiao": "Lages", "total_demandas": 5938},
        {"codarea": "4204", "nome_regiao": "Chapecó", "total_demandas": 9948},
        {"codarea": "4205", "nome_regiao": "Caçador", "total_demandas": 2488},
        {"codarea": "4206", "nome_regiao": "Joinville", "total_demandas": 16842},
        {"codarea": "4207", "nome_regiao": "Blumenau", "total_demandas": 27812},
    ]
    df = pd.DataFrame(dados_sc)

    custom_teal = [
        [0.0, "#99f6e4"],  # Teal claro bem visível
        [0.35, "#2dd4bf"],
        [0.7, "#0d9488"],
        [1.0, "#115e59"]   # Teal profundo
    ]

    print("3. Construindo mapa coroplético das 7 regiões...")
    fig = px.choropleth(
        df,
        geojson=geojson_intermed,
        locations="codarea",
        featureidkey="properties.codarea",
        color="total_demandas",
        color_continuous_scale=custom_teal,
        hover_name="nome_regiao",
        hover_data={"total_demandas": ":,", "codarea": False},
        title="<b>Regiões Intermediárias de Santa Catarina</b><br><sup>Total: 7 Regiões Oficiais | Fonte: IBGE</sup>",
        labels={"total_demandas": "Total de Demandas"}
    )

    fig.update_geos(
        fitbounds="locations",
        visible=False
    )

    fig.update_traces(
        marker_line_width=1.5,
        marker_line_color="#1e293b"
    )

    fig.update_layout(
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        autosize=True
    )
    
    output_html = "mapa_sc_regioes_intermediarias_plotly.html"
    fig.write_html(output_html, include_plotlyjs=True)
    print(f"✅ Mapa das 7 Regiões de Santa Catarina salvo com sucesso em '{output_html}'!")

if __name__ == "__main__":
    main()
