---
name: ibge-data-analysis
description: >-
  Comprehensive guide, runbooks, and high-performance Python client for fetching, merging,
  and visualizing data from both official IBGE APIs: Localidades (Países, Regiões, Estados,
  Mesorregiões, Microrregiões, Regiões Intermediárias, Regiões Imediatas, Municípios, Distritos,
  Subdistritos) and Malhas Geográficas v4 (GeoJSON, SVG, spatial geometries across all administrative
  scales). Use this skill whenever the user asks to enrich tabular data with IBGE metadata,
  perform geospatial analysis, create choropleth maps, or use GeoPandas, Polars, Pandas, Plotly,
  Folium, and Matplotlib.
---

# IBGE Data Analysis & Geospatial Intelligence Skill (Santa Catarina - SC)

Este guia fornece procedimentos práticos, documentação técnica exaustiva e um cliente Python completo com cache integrado para explorar **100% dos recursos** das duas APIs oficiais do IBGE, com **todos os exemplos e receitas focados no estado de Santa Catarina (SC / Código 42)**:
1. **API de Localidades** (`https://servicodados.ibge.gov.br/api/v1/localidades`): Estrutura hierárquica e divisão dos 295 municípios e das 7 regiões intermediárias de Santa Catarina.
2. **API de Malhas Geográficas v4** (`https://servicodados.ibge.gov.br/api/v4/malhas`): Limites territoriais vetoriais (GeoJSON) dos municípios e regiões intermediárias com correção automática de anéis poligonais.

---

## Dicas de Contraste e Visibilidade Vetorial no Plotly

Para garantir que todos os municípios fiquem **100% visíveis contra o fundo branco** (mesmo municípios com indicadores mínimos), use:
1. **Escala de cor com piso visível**: Comece a escala em um tom nítido (ex: `#93c5fd` - azul celeste visível) em vez de tons esbranquiçados (`#f7fbff`).
2. **Bordas nítidas**: Utilize contorno em tom ardósia (`marker_line_color="#334155"`, `marker_line_width=0.7`) para delimitar com precisão cada cidade.
3. **Enquadramento perfeito**: Utilize `fitbounds="locations"` e `visible=False`.

```python
custom_blues = [
    [0.0, "#93c5fd"],  # Piso bem visível (nunca branco)
    [0.3, "#60a5fa"],
    [0.6, "#2563eb"],
    [1.0, "#1e3a8a"]   # Azul marinho
]

fig.update_traces(
    marker_line_width=0.7,
    marker_line_color="#334155"
)
```

---

## Receitas de Código em Santa Catarina

### Receita 1: Mapa dos 295 Municípios de Santa Catarina

```python
import plotly.express as px
import pandas as pd
import requests

# 1. GeoJSON oficial dos 295 municípios de SC
url_malha = "https://servicodados.ibge.gov.br/api/v4/malhas/estados/42?formato=application/vnd.geo+json&intrarregiao=municipio&qualidade=minima"
geojson_sc = requests.get(url_malha).json()

# Inverte anéis para D3/Plotly
for feat in geojson_sc.get("features", []):
    geom = feat.get("geometry", {})
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "Polygon":
        geom["coordinates"] = [ring[::-1] for ring in coords]
    elif t == "MultiPolygon":
        geom["coordinates"] = [[ring[::-1] for ring in poly] for poly in coords]

# 2. Dados dos municípios de SC
url_loc = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/42/municipios?view=nivelado"
df_sc = pd.DataFrame(requests.get(url_loc).json())
df_sc["codarea"] = df_sc["municipio-id"].astype(str)
df_sc["indicador"] = [70 + (i * 5 % 28) for i in range(len(df_sc))]

custom_blues = [
    [0.0, "#93c5fd"],
    [0.3, "#60a5fa"],
    [0.6, "#2563eb"],
    [1.0, "#1e3a8a"]
]

# 3. Renderiza mapa coroplético de alto contraste
fig = px.choropleth(
    df_sc,
    geojson=geojson_sc,
    locations="codarea",
    featureidkey="properties.codarea",
    color="indicador",
    color_continuous_scale=custom_blues,
    hover_name="municipio-nome",
    title="<b>Municípios de Santa Catarina</b><br><sup>Total: 295 Municípios | Fonte: IBGE</sup>"
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_traces(marker_line_width=0.7, marker_line_color="#334155")
fig.update_layout(margin=dict(l=20, r=20, t=60, b=20), paper_bgcolor="#ffffff")
fig.write_html("mapa_sc_municipios_plotly.html", include_plotlyjs=True)
```

---

### Receita 2: Mapa das 7 Regiões Intermediárias de SC (Sem Vazios)

```python
import plotly.express as px
import pandas as pd
import requests

url_malha = "https://servicodados.ibge.gov.br/api/v4/malhas/estados/42?formato=application/vnd.geo+json&intrarregiao=regiao-intermediaria&qualidade=minima"
geojson_intermed = requests.get(url_malha).json()

for feat in geojson_intermed.get("features", []):
    geom = feat.get("geometry", {})
    t = geom.get("type")
    coords = geom.get("coordinates", [])
    if t == "Polygon":
        geom["coordinates"] = [ring[::-1] for ring in coords]
    elif t == "MultiPolygon":
        geom["coordinates"] = [[ring[::-1] for ring in poly] for poly in coords]

# As 7 regioes intermediarias oficiais de SC.
# ATENCAO: os valores de `indicador` abaixo sao FICTICIOS, apenas para o exemplo
# renderizar. Substitua pela sua propria agregacao antes de usar; numeros de
# exemplo com aparencia plausivel ja foram confundidos com dado real neste
# projeto.
df = pd.DataFrame([
    {"codarea": "4201", "nome": "Florianópolis", "indicador": 70},
    {"codarea": "4202", "nome": "Criciúma", "indicador": 62},
    {"codarea": "4203", "nome": "Lages", "indicador": 55},
    {"codarea": "4204", "nome": "Chapecó", "indicador": 48},
    {"codarea": "4205", "nome": "Caçador", "indicador": 41},
    {"codarea": "4206", "nome": "Joinville", "indicador": 84},
    {"codarea": "4207", "nome": "Blumenau", "indicador": 91},
])

fig = px.choropleth(
    df,
    geojson=geojson_intermed,
    locations="codarea",
    featureidkey="properties.codarea",
    color="indicador",
    color_continuous_scale="Tealgrn",
    hover_name="nome",
    title="<b>Regiões Intermediárias de Santa Catarina</b><br><sup>Total: 7 Regiões Oficiais | Fonte: IBGE</sup>"
)
fig.update_geos(fitbounds="locations", visible=False)
fig.update_traces(marker_line_width=1.5, marker_line_color="#1e293b")
fig.update_layout(margin=dict(l=20, r=20, t=60, b=20), paper_bgcolor="#ffffff")
fig.write_html("mapa_sc_regioes_intermediarias_plotly.html", include_plotlyjs=True)
```

---

## Arquivos da Skill

- [examples/municipalities_choropleth_plotly.py](./examples/municipalities_choropleth_plotly.py): Gera o mapa dos 295 municípios de SC com alto contraste.
- [examples/choropleth_map_plotly.py](./examples/choropleth_map_plotly.py): Gera o mapa das 7 Regiões Intermediárias de SC.
- [examples/merge_disque100_ibge.py](./examples/merge_disque100_ibge.py): Análise e agregação das denúncias de SC com Polars.
- [scripts/ibge_client.py](./scripts/ibge_client.py): Cliente Python com cache automático e correção de polígonos.
