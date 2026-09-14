#!/usr/bin/env python3
"""
=============================================================================
Exemplo Prático: Mapa Interativo de Santa Catarina com Folium + IBGE
=============================================================================
Gera um mapa web interativo com Folium focado em Santa Catarina (SC),
contendo camada coroplética e tooltips em hover com o nome do município,
região intermediária e indicador.
=============================================================================
"""

import sys
import folium
from folium.features import GeoJsonTooltip
import pandas as pd
from pathlib import Path

# Adiciona diretório de scripts para importar o client
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from ibge_client import IBGEClient

def main():
    client = IBGEClient()
    uf_alvo = "SC"
    
    print(f"1. Obtendo GeoJSON dos 295 municípios de Santa Catarina ({uf_alvo})...")
    geojson_sc = client.get_malha_municipios_uf_geojson(uf=uf_alvo, qualidade="minima")

    print("2. Obtendo tabela oficial de municípios de Santa Catarina via Localidades...")
    df_loc = client.get_municipios_df(uf=uf_alvo, engine="pandas")

    print("3. Preparando métricas e enriquecendo features GeoJSON para tooltips...")
    info_map = {}
    for i, r in df_loc.iterrows():
        cid = str(r["municipio-id"])
        info_map[cid] = {
            "nome": r["municipio-nome"],
            "regiao_imediata": r["regiao-imediata-nome"],
            "regiao_intermediaria": r["regiao-intermediaria-nome"],
            "taxa_resolucao": 60 + (i * 7 % 38)
        }

    for f in geojson_sc["features"]:
        cid = str(f["properties"]["codarea"])
        if cid in info_map:
            f["properties"]["nome"] = info_map[cid]["nome"]
            f["properties"]["regiao_imediata"] = info_map[cid]["regiao_imediata"]
            f["properties"]["regiao_intermediaria"] = info_map[cid]["regiao_intermediaria"]
            f["properties"]["taxa_resolucao"] = info_map[cid]["taxa_resolucao"]
        else:
            f["properties"]["nome"] = "N/D"
            f["properties"]["regiao_imediata"] = "N/D"
            f["properties"]["regiao_intermediaria"] = "N/D"
            f["properties"]["taxa_resolucao"] = 0

    df_dados = pd.DataFrame([
        {"codarea": k, "taxa_resolucao": v["taxa_resolucao"]} for k, v in info_map.items()
    ])

    print("4. Renderizando mapa no Folium (Centralizado em Santa Catarina)...")
    # Coordenadas do centro geográfico de Santa Catarina
    mapa_sc = folium.Map(location=[-27.24, -50.21], zoom_start=8, tiles="CartoDB positron")

    # Camada coroplética
    folium.Choropleth(
        geo_data=geojson_sc,
        name="Taxa de Resolução (%)",
        data=df_dados,
        columns=["codarea", "taxa_resolucao"],
        key_on="feature.properties.codarea",
        fill_color="YlGnBu",
        fill_opacity=0.75,
        line_opacity=0.4,
        legend_name="Taxa de Resolução em Santa Catarina (%)",
        highlight=True
    ).add_to(mapa_sc)

    # Tooltip interativo ao passar o mouse sobre os 295 municípios
    folium.GeoJson(
        geojson_sc,
        style_function=lambda x: {"fillColor": "#ffffff00", "color": "#00000000"},
        tooltip=GeoJsonTooltip(
            fields=["nome", "regiao_imediata", "regiao_intermediaria", "taxa_resolucao"],
            aliases=["Município:", "Região Imediata:", "Região Intermediária:", "Taxa (%):"],
            localize=True,
            sticky=False,
            labels=True
        )
    ).add_to(mapa_sc)

    folium.LayerControl().add_to(mapa_sc)

    output_file = "mapa_sc_folium.html"
    mapa_sc.save(output_file)
    print(f"✅ Mapa Folium interativo de Santa Catarina salvo em '{output_file}'!")

if __name__ == "__main__":
    main()
