# Manual Técnico Completo: API de Localidades do IBGE

Base URL: `https://servicodados.ibge.gov.br/api/v1/localidades`

A API de Localidades provê acesso programmatico à estrutura completa da divisão político-administrativa e dos recortes territoriais do Brasil.

---

## 1. Entidades Territoriais e Endpoints

### 1.1 Países
- `GET /paises`: Retorna lista de países cadastrados com código M49 e ISO-ALPHA-2.
- `GET /paises/{id}`: Consulta por código ou sigla (ex: `GET /paises/76` para Brasil).

### 1.2 Regiões (Macrorregiões do Brasil)
- `GET /regioes`: Retorna as 5 regiões oficiais:
  - `1`: Norte (N)
  - `2`: Nordeste (NE)
  - `3`: Sudeste (SE)
  - `4`: Sul (S)
  - `5`: Centro-Oeste (CO)
- `GET /regioes/{id}/estados`: Retorna os estados pertencentes àquela região.
- `GET /regioes/{id}/municipios`: Retorna todos os municípios daquela região.

### 1.3 Estados (Unidades da Federação - UFs)
- `GET /estados`: Retorna as 27 UFs do Brasil (com sigla, nome e região).
- `GET /estados/{UF}`: Consulta por sigla (`SP`, `RJ`, `MG`) ou código IBGE (`35`, `33`, `31`).
- `GET /estados/{UF}/municipios`: Todos os municípios da UF.
- `GET /estados/{UF}/mesorregioes`: Mesorregiões da UF.
- `GET /estados/{UF}/microrregioes`: Microrregiões da UF.
- `GET /estados/{UF}/regioes-intermediarias`: Regiões intermediárias da UF.
- `GET /estados/{UF}/regioes-imediatas`: Regiões imediatas da UF.
- `GET /estados/{UF}/distritos`: Distritos da UF.

### 1.4 Regiões Geográficas Intermediárias e Imediatas (Divisão de 2017)
- `GET /regioes-intermediarias`: Todas as 133 Regiões Intermediárias do Brasil.
- `GET /regioes-intermediarias/{id}/municipios`: Municípios da Região Intermediária.
- `GET /regioes-imediatas`: Todas as 510 Regiões Imediatas do Brasil.
- `GET /regioes-imediatas/{id}/municipios`: Municípios da Região Imediata.

### 1.5 Mesorregiões e Microrregiões (Divisão Tradicional de 1989)
- `GET /mesorregioes`: Todas as 137 Mesorregiões.
- `GET /mesorregioes/{id}/municipios`: Municípios da mesorregião.
- `GET /microrregioes`: Todas as 558 Microrregiões.
- `GET /microrregioes/{id}/municipios`: Municípios da microrregião.

### 1.6 Municípios
- `GET /municipios`: Todos os 5.570 municípios brasileiros.
- `GET /municipios/{id}`: Detalhes de um município pelo código IBGE de 7 dígitos.
- `GET /municipios/{id}/distritos`: Distritos que compõem o município.
- `GET /municipios/{id}/subdistritos`: Subdistritos que compõem o município.

### 1.7 Distritos e Subdistritos
- `GET /distritos`: Todos os distritos do Brasil.
- `GET /subdistritos`: Todos os subdistritos do Brasil.

---

## 2. Consultas Múltiplas com Pipe (`|`)

A API do IBGE suporta consultar múltiplos IDs separando por pipe (`|`):
- `GET /estados/33|35/municipios`: Retorna todos os municípios do Rio de Janeiro e de São Paulo em uma única requisição.
- `GET /regioes/1|5/estados`: Retorna os estados do Norte e do Centro-Oeste.

---

## 3. Parâmetros Globais e Modo Nivelado (`view=nivelado`)

| Parâmetro | Valores | Utilidade |
| :--- | :--- | :--- |
| `view` | `nivelado` | **Fundamental para DataFrames**. Achata o JSON em colunas simples com hífen. |
| `orderBy` | `nome`, `id` | Ordenação alfabética pelo nome ou crescente pelo ID numérico. |

### Comparativo de Retorno (`view=padrao` vs `view=nivelado`):

#### Padrão (Aninhado - Difícil de tabular):
```json
{
  "id": 3550308,
  "nome": "São Paulo",
  "microrregiao": {
    "id": 35061,
    "nome": "São Paulo",
    "mesorregiao": {
      "id": 3515,
      "nome": "Metropolitana de São Paulo",
      "UF": {
        "id": 35,
        "sigla": "SP",
        "nome": "São Paulo",
        "regiao": {"id": 3, "sigla": "SE", "nome": "Sudeste"}
      }
    }
  }
}
```

#### Nivelado (`view=nivelado` - Perfeito para Polars/Pandas):
```json
{
  "municipio-id": 3550308,
  "municipio-nome": "São Paulo",
  "microrregiao-id": 35061,
  "microrregiao-nome": "São Paulo",
  "mesorregiao-id": 3515,
  "mesorregiao-nome": "Metropolitana de São Paulo",
  "regiao-imediata-id": 350001,
  "regiao-imediata-nome": "São Paulo",
  "regiao-intermediaria-id": 3501,
  "regiao-intermediaria-nome": "São Paulo",
  "UF-id": 35,
  "UF-sigla": "SP",
  "UF-nome": "São Paulo",
  "regiao-id": 3,
  "regiao-sigla": "SE",
  "regiao-nome": "Sudeste"
}
```
