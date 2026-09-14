# Disque 100 em Santa Catarina

Painel analítico sobre as denúncias do Disque 100 em Santa Catarina, de 2011 a 2026.
Faz a triagem entre ocorrências com indício de infração penal e demandas
socioassistenciais, e cruza esses dados com a população do Censo 2022 do IBGE e com
a rede da Polícia Científica do estado (PCI-SC).

## Como ler os números antes de usá-los

Cada linha dos microdados publicados pelo MDHC é uma combinação de **violação,
vítima e suspeito**, e não uma denúncia. Em 2026, Santa Catarina tem 95.850 registros
de violação para 13.140 denúncias distintas. O número de registros por denúncia subiu
de 2,3 em 2020 para 7,3 em 2026 e varia de 4,5 a 9,9 entre municípios.

Por isso o painel trabalha com duas unidades, sempre rotuladas na tela:

| Unidade | O que conta | Cobertura |
| :--- | :--- | :--- |
| Denúncias únicas | Identificador oficial da denúncia | 2021 a 2026 |
| Registros de violação | Linhas dos microdados | 2011 a 2026 |

Denúncias únicas é a unidade comparável com os balanços publicados pelo MDHC.
Contagens de registro de violação não são comparáveis entre anos nem entre municípios.

O relatório em `data/processed/sc_relatorio_auditoria_dados.json` traz o inventário
dos 22 arquivos de origem, a cobertura de cada indicador por semestre, a comparação
com o balanço oficial de 2011 a 2019, as limitações conhecidas e o SHA-256 de cada
artefato. A aba "Metodologia e auditoria" do painel exibe esse relatório.

## Início rápido

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run streamlit_app/app.py # http://localhost:8501
```

O repositório já traz a base processada em `data/` e `data/database/`, portanto o
painel sobe sem executar o pipeline.

## Reconstruir a base

Os passos dependem um do outro nesta ordem. O último fecha a tabela de hashes da
auditoria, quando todos os artefatos já existem na versão final.

```bash
python3 scripts/gerar_banco_duckdb_sc.py            # fato, dimensões, KPIs, auditoria
python3 scripts/build_annual_kpis.py                # KPIs por município, ano e semestre
python3 scripts/gerar_geo_pci_sc.py                 # malha do IBGE, distâncias, eixos rodoviários
python3 scripts/analisar_distribuicao_penal_sc.py   # métricas derivadas e hashes finais
```

Passos opcionais:

```bash
python3 scripts/sync_disque100.py                            # baixa os microdados do gov.br
python3 scripts/scrape_policia_cientifica_sc.py              # atualiza as unidades da PCI-SC
python3 scripts/generate_sc_disque100_folium_dashboard.py    # mapa detalhado em HTML
python3 scripts/gerar_notebook_analise.py                    # regera o notebook
```

## Notebook

`notebooks/analise_completa_disque100_sc.ipynb` documenta a análise que sustenta o
painel: granularidade dos microdados, fator de expansão entre registro e denúncia,
comparação entre as três eras de esquema, cobertura dos indicadores por semestre,
validação contra o balanço oficial e o denominador populacional das taxas.

```bash
jupyter lab notebooks/analise_completa_disque100_sc.ipynb
# ou, para reexecutar e regravar as saídas:
jupyter nbconvert --execute --inplace notebooks/analise_completa_disque100_sc.ipynb
```

## Outros artefatos

- `pitch.html` — apresentação executiva em slides, acompanha `Pitch - Grupo 03.pdf`
- `dashboards/dashboard_sc_disque100_folium.html` — mapa detalhado com agrupamentos,
  eixos rodoviários e unidades periciais
- `dashboards/dashboard_executivo_grupos_sc.html` — painel comparativo por grupo

## Estrutura

```text
├── streamlit_app/    Painel: config, carregamento, componentes, abas e gráficos
├── scripts/          Pipeline: ingestão, classificação, agregação, geoprocessamento
├── data/
│   ├── raw/          Microdados do Disque 100 e balanços temáticos do MDHC
│   ├── processed/    Fato, dimensões, KPIs, malha, matriz de distância, auditoria
│   └── database/     Base analítica em DuckDB e SQLite
├── notebooks/        Análise exploratória com saídas gravadas
└── dashboards/       Mapas e painéis em HTML
```

## Consulta direta à base

```python
import duckdb

con = duckdb.connect("data/database/sc_disque100_analitico.duckdb", read_only=True)
con.execute("SHOW TABLES").fetchall()
# dim_municipios, dim_unidades_pci, fato_denuncias,
# kpis_categoria_penal, kpis_grupos_municipios, kpis_grupos_municipios_ano

con.execute("""
    SELECT ano,
           COUNT(*) AS registros_violacao,
           COUNT(DISTINCT CASE WHEN grain_denuncia_confiavel = 1 THEN id_denuncia END)
               AS denuncias_unicas
    FROM fato_denuncias GROUP BY ano ORDER BY ano
""").fetchdf()
```

## Fontes

| Fonte | Conteúdo |
| :--- | :--- |
| MDHC / Ouvidoria Nacional de Direitos Humanos | Microdados abertos do Disque 100, 2011 a 2026, e balanços temáticos |
| IBGE, Censo Demográfico 2022 (SIDRA 4714) | População residente dos 295 municípios |
| IBGE, API de Malhas e de Localidades | Malha municipal e divisão em regiões intermediárias e imediatas |
| Polícia Científica de Santa Catarina | Catálogo das 30 unidades: 9 superintendências e 21 núcleos |

## Limitações

- A classificação penal é automatizada por taxonomia de palavras-chave sobre o texto
  da violação relatada. Indica onde há indício a apurar; não é decisão jurídica, não
  foi validada contra laudo ou inquérito, e sua precisão não foi medida.
- O percentual penal não é comparável ao longo da série: o vocabulário de violação
  muda entre as eras de esquema.
- 2026 tem apenas o primeiro semestre. As taxas são anualizadas; os totais absolutos
  desse ano ficam abaixo do patamar real.
- As distâncias até as unidades periciais são geodésicas, em linha reta. Não são
  distâncias rodoviárias e não sustentam estimativa de tempo de deslocamento.
- Os grupos vulneráveis não são mutuamente exclusivos e não somam o total. O módulo
  "Violência contra a Mulher" só existe nos microdados a partir de 2025.
- O denominador das taxas é a população de um único ano, o Censo 2022.
- Denúncia registrada não equivale a violação confirmada. A base mede demanda
  notificada e é sensível à subnotificação, que varia por território e por grupo.

Grupo 03, Ciência de Dados, UFSC.
