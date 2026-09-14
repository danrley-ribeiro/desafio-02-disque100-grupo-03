# Manual Técnico Completo: API de Malhas Geográficas v4 do IBGE

Base URL: `https://servicodados.ibge.gov.br/api/v4/malhas`

A API de Malhas Geográficas do IBGE disponibiliza as bases cartográficas vetoriais contendo as geometrias dos limites territoriais oficiais do Brasil.

---

## 1. Matriz Completa de Escopos e Subdivisões (`intrarregiao`)

O parâmetro `intrarregiao` determina como o polígono solicitado será particionado internamente:

| Endpoint Base | `intrarregiao` Aceitos | Descrição do Retorno | Features Típicas |
| :--- | :--- | :--- | :---: |
| **`/paises/BR`** | *(nenhum)* | Polígono único do contorno do Brasil | 1 |
| | `intrarregiao=regiao` | As 5 Macrorregiões do Brasil | 5 |
| | `intrarregiao=UF` | Todos os 27 Estados do Brasil | 27 |
| | `intrarregiao=regiao-intermediaria` | Todas as 133 Regiões Intermediárias | 133 |
| | `intrarregiao=regiao-imediata` | Todas as 510 Regiões Imediatas | 510 |
| | `intrarregiao=municipio` | Todos os 5.570 Municípios do Brasil | 5.571 |
| **`/regioes/{id}`** (1 a 5) | *(nenhum)* | Contorno da Macrorregião | 1 |
| | `intrarregiao=UF` | Estados daquela Macrorregião | 3 a 9 |
| | `intrarregiao=regiao-intermediaria` | Regiões intermediárias da Macrorregião | 10 a 40 |
| | `intrarregiao=regiao-imediata` | Regiões imediatas da Macrorregião | 40 a 180 |
| | `intrarregiao=municipio` | Todos os municípios da Macrorregião | 450 a 1.668 |
| **`/estados/{UF}`** (11 a 53) | *(nenhum)* | Contorno do Estado | 1 |
| | `intrarregiao=regiao-intermediaria` | Regiões intermediárias do Estado | 2 a 13 |
| | `intrarregiao=regiao-imediata` | Regiões imediatas do Estado | 4 a 53 |
| | `intrarregiao=municipio` | Todos os municípios daquela UF | 15 a 853 |
| **`/municipios/{id}`** (7 dígitos)| *(nenhum)* | Contorno do município específico | 1 |

---

## 2. Parâmetros de Formato, Qualidade e Edição Temporal

### 2.1 `formato`
- `application/vnd.geo+json`: Retorna um `FeatureCollection` (GeoJSON RFC 7946). Compatível com GeoPandas, Plotly, Folium, PyDeck, Mapbox, D3 e Leaflet.
- `image/svg+xml`: Retorna uma imagem SVG vetorial renderizada diretamente.
- `application/zip`: Retorna um arquivo ZIP contendo Shapefiles (.shp, .shx, .dbf, .prj) ou TopoJSON.

### 2.2 `qualidade` (Nível de Generalização Cartográfica)
- `minima`: **Altamente recomendada para dashboards, notebooks e mapas web**. Reduz drasticamente a quantidade de nós mantendo os limites reconhecíveis. Carrega em menos de 1 segundo.
- `intermediaria`: Resolução equilibrada para mapas estáticos e relatórios.
- `maxima`: Geometria original sem simplificação (usada para cálculos geodésicos e análises de intersecção exata).

### 2.3 `edicao` / Ano de Referência da Malha
- Por padrão, a API retorna a malha territorial da versão mais recente disponibilizada pelo Censo/IBGE.
- Pode-se especificar o ano da malha com `edicao=2022`, `edicao=2020`, `edicao=2018`, etc.

---

## 3. Sistema de Referência de Coordenadas (CRS)

- As coordenadas no GeoJSON do IBGE são expressas em **Graus Decimais (Latitude/Longitude)**.
- Datum oficial do Brasil: **SIRGAS 2000 (EPSG:4674)**, compatível e intercambiável com **WGS 84 (EPSG:4326)** para a esmagadora maioria das visualizações em tela.

---

## 4. Estrutura do Objeto GeoJSON Retornado

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon", // ou MultiPolygon para estados costeiros com ilhas
        "coordinates": [...]
      },
      "properties": {
        "codarea": "35" // Código IBGE da área (2 dígitos para UF, 7 dígitos para Município)
      }
    }
  ]
}
```

> **Dica para Plotly / Folium:**
> Aponte sempre a chave do GeoJSON para `featureidkey="properties.codarea"` (no Plotly) ou `key_on="feature.properties.codarea"` (no Folium).
