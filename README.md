# Sistema de Inteligência Territorial do Disque 100 - Governo de Santa Catarina

Sistema analítico avançado de inteligência territorial para triagem penal, monitoramento de grupos vulneráveis e distribuição geoespacial de denúncias do **Disque 100 / Ouvidoria Nacional de Direitos Humanos (ONDH)** para os 295 municípios do Estado de Santa Catarina (2011 a 2026).

O projeto integra técnicas de Ciência de Dados de alta performance (**DuckDB, Polars, Parquet, Streamlit, Folium, Plotly**) cruzadas com a base demográfica oficial do **Censo IBGE 2022** e com as 30 unidades periciais da **Polícia Científica de Santa Catarina (PCI-SC)**.

---

## 📁 Estrutura do Projeto

O repositório está organizado segundo as melhores práticas de Engenharia de Dados e Governança:

```text
desafio-02-disque100-grupo-03/
├── dashboards/                  # Painéis executivos interativos e relatórios visuais
│   ├── app_sc_disque100_streamlit.py                  # Painel completo Streamlit (5 abas interativas)
│   ├── apresentacao_executiva_indicios_penais_sc.html # Pitch deck governamental interativo
│   ├── dashboard_executivo_grupos_sc.html             # Resumo executivo de indicadores por grupo
│   ├── dashboard_sc_disque100_folium.html             # Mapa cartográfico Folium georreferenciado
│   ├── mapa_sc_municipios_folium.html                 # Mapa interativo municipal
│   ├── mapa_sc_municipios_plotly.html                 # Mapa coroplético vetorial municipal (Plotly)
│   └── mapa_sc_regioes_intermediarias_plotly.html     # Mapa coroplético das 7 regiões intermediárias
├── data/                        # Camadas de dados estruturadas (Data Lakehouse)
│   ├── raw/                     # Camada Bronze: dados brutos imutáveis
│   │   ├── balancos-gerais/     # 9 pastas com microdados temáticos originais em CSV
│   │   └── disque100-*.parquet  # 22 arquivos Parquet históricos de 2011 a 2026
│   ├── processed/               # Camada Prata: dados limpos, enriquecidos e auditados
│   │   ├── sc_fato_denuncias.parquet              # Tabela fato com 699.029 denúncias classificadas
│   │   ├── sc_dim_municipios.parquet              # Dimensão dos 295 municípios com dados do Censo 2022
│   │   ├── sc_dim_pci.parquet                     # Dimensão das 30 unidades da Polícia Científica
│   │   ├── sc_kpis_grupos_municipios.parquet/.csv # Métricas consolidadas por município
│   │   ├── sc_kpis_grupos_municipios_ano.parquet  # Série temporal de KPIs municipais por ano
│   │   ├── sc_censo_2022_populacao.json           # Dicionário populacional oficial do IBGE
│   │   ├── unidades_policia_cientifica_sc.json    # Geocodificação das unidades forenses da PCI-SC
│   │   ├── sc_municipios_distancia_pci.json       # Matriz de distâncias aos núcleos periciais
│   │   ├── sc_distribuicao_penal_metricas.json    # Agregações de famílias delitivas
│   │   └── sc_relatorio_auditoria_dados.json      # Certificado de integridade e hashes SHA-256
│   └── database/                # Camada Ouro: bancos analíticos otimizados
│       ├── sc_disque100_analitico.duckdb          # Banco colunar auditado com 5 tabelas analíticas
│       └── sc_disque100_analitico.sqlite          # Banco relacional indexado
├── notebooks/                   # Jupyter Notebooks analíticos
│   └── analise_completa_disque100_sc.ipynb                # Caderno reprodutível com 24 etapas analíticas
├── scripts/                     # Pipelines ETL, processamento e automação
│   ├── gerar_banco_duckdb_sc.py                  # Pipeline mestre de criação e auditoria da base DuckDB
│   ├── analisar_distribuicao_penal_sc.py         # Motor de cálculo e ranking de vulnerabilidade penal
│   ├── classificar_indicio_penal.py              # Algoritmo de triagem: Ilícito Penal vs Apoio Social
│   ├── generate_sc_disque100_folium_dashboard.py # Gerador da camada cartográfica Folium
│   ├── build_annual_kpis.py                      # Agregador temporal anual por município
│   ├── scrape_policia_cientifica_sc.py           # Coletor e geocodificador das unidades da PCI-SC
│   ├── csv2parquet.py                            # Conversor de alto desempenho CSV -> Parquet
│   ├── sync_disque100.py                         # Sincronizador de microdados abertos federais
│   └── sync_balancos.py                          # Sincronizador dos balanços gerais temáticos
├── tests/                       # Testes de integração e validação visual
│   ├── test_suite_visual.js                      # Teste automatizado de renderização via Puppeteer
│   ├── test_clean_hover.js                       # Validação dos tooltips Leaflet
│   └── verify_map_reactivity.js                  # Validação de reatividade do Streamlit no Chrome
├── .streamlit/                  # Configurações de tema e porta do Streamlit
├── .gitignore                   # Regras de exclusão de artefatos temporários
├── requirements.txt             # Dependências do ecossistema Python
├── package.json                 # Dependências Node.js (Puppeteer para testes)
└── README.md                    # Este arquivo
```

---

## 🚀 Como Executar

### 1. Pré-requisitos e Instalação

Certifique-se de ter o Python 3.10+ instalado. Ative o ambiente virtual e instale as dependências:

```bash
# Ativar o ambiente virtual
source .venv/bin/activate

# Instalar dependências Python (se necessário)
pip install -r requirements.txt
```

Para executar os testes visuais automatizados (opcional):
```bash
npm install
```

---

### 2. Executando o Dashboard Streamlit (Principal)

O painel principal interativo oferece 5 abas de análise (Visão Geral, Grupos Vulneráveis, Triagem Penal, Polícia Científica e Auditoria):

```bash
streamlit run dashboards/app_sc_disque100_streamlit.py
```
Acesse no navegador: `http://localhost:8501`

---

### 3. Visualizando os Dashboards e Relatórios HTML

Os arquivos HTML em `dashboards/` são totalmente autocontidos e podem ser abertos diretamente em qualquer navegador:

- **Apresentação Executiva (Pitch Deck)**: `dashboards/apresentacao_executiva_indicios_penais_sc.html`
- **Dashboard Cartográfico Folium**: `dashboards/dashboard_sc_disque100_folium.html`
- **Painel Executivo de Grupos**: `dashboards/dashboard_executivo_grupos_sc.html`
- **Mapas Plotly**: `dashboards/mapa_sc_municipios_plotly.html` e `dashboards/mapa_sc_regioes_intermediarias_plotly.html`

---

### 4. Consultas Diretas no DuckDB

Você pode consultar instantaneamente a base colunar de 699 mil registros via terminal ou Python:

```python
import duckdb

con = duckdb.connect("data/database/sc_disque100_analitico.duckdb", read_only=True)

# Listar tabelas disponíveis
print(con.execute("SHOW TABLES").fetchall())

# Exemplo: Top 5 municípios com maior taxa de denúncias penais em crianças
df = con.execute("""
    SELECT municipio, populacao_censo_2022, criancas_penal,
           ROUND((criancas_penal * 10000.0 / populacao_censo_2022), 2) AS taxa_crianca_10k
    FROM kpis_grupos_municipios
    ORDER BY taxa_crianca_10k DESC
    LIMIT 5
""").df()
print(df)
con.close()
```

---

### 5. Execução dos Testes Automatizados

Para validar o funcionamento da interface, tooltips e renderização do Chrome:

```bash
node tests/test_suite_visual.js
```

---

## 🏛️ Fontes Oficiais Governamentais (Gov.br)

| Órgão / Portal | Link Oficial | Descrição no Pipeline |
| :--- | :--- | :--- |
| **Ministério dos Direitos Humanos e da Cidadania (MDHC)** | [https://www.gov.br/mdh/pt-br/ondh](https://www.gov.br/mdh/pt-br/ondh) | Painel de Dados da Ouvidoria Nacional de Direitos Humanos e microdados abertos do Disque 100. |
| **Ministério da Justiça e Segurança Pública (MJSP)** | [https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/senasp](https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/senasp) | Sistema Nacional de Informações de Segurança Pública (SENASP) e protocolos de investigação. |
| **Ministério do Desenvolvimento Social (MDS)** | [https://www.gov.br/mds/pt-br/acoes-e-programas/assistencia-social/unidades-de-atendimento/cras-e-creas](https://www.gov.br/mds/pt-br/acoes-e-programas/assistencia-social/unidades-de-atendimento/cras-e-creas) | Tipificação Nacional de Serviços Socioassistenciais (CRAS e CREAS). |
| **Instituto Brasileiro de Geografia e Estatística (IBGE)** | [https://sidra.ibge.gov.br/tabela/4714](https://sidra.ibge.gov.br/tabela/4714) | Censo Demográfico 2022: População oficial residente dos 295 municípios catarinenses. |
| **Polícia Científica de Santa Catarina (PCI-SC)** | [https://www.policiacientifica.sc.gov.br](https://www.policiacientifica.sc.gov.br/) | Estrutura organizacional das 7 superintendências regionais e 23 núcleos periciais. |
| **Polícia Civil de Santa Catarina (PCSC)** | [https://www.pc.sc.gov.br](https://www.pc.sc.gov.br/) | Mapeamento das Delegacias de Proteção à Criança, Adolescente, Mulher e Idoso (DPCAMI). |

---

## 🔒 Auditoria e Governança

Todas as tabelas geradas contam com hash de integridade SHA-256 e rastreabilidade total desde os microdados brutos do governo federal até a consolidação final no DuckDB, em conformidade com as diretrizes da LGPD (Lei Geral de Proteção de Dados) e do Governo do Estado de Santa Catarina.

