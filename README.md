# 🛡️ Sistema de Inteligência Territorial do Disque 100 (SC)
O sistema realiza **triagem automática** entre ilícitos penais e demandas socioassistenciais, cruzando dados históricos com a demografia do **Censo IBGE 2022** e com as 30 unidades da **Polícia Científica de SC (PCI-SC)**.

---

## ⚡ Início Rápido

### 1. Criar e Ativar o Ambiente Virtual
```bash
# Criar o ambiente virtual (.venv)
python3 -m venv .venv

# Ativar o ambiente
# No Linux/macOS:
source .venv/bin/activate
# No Windows:
# .venv\Scripts\activate

# Instalar as dependências
pip install -r requirements.txt
```

### 2. Executar o Painel Streamlit
```bash
streamlit run streamlit_app/app.py
```
> Ou pelo atalho legado: `streamlit run dashboards/app_sc_disque100_streamlit.py`
> Acesse no navegador: `http://localhost:8501`

### 3. Visualizar Relatórios e Mapas HTML
Os arquivos da pasta `dashboards/` são autocontidos e abrem diretamente no navegador:
- **`apresentacao_executiva_indicios_penais_sc.html`**: Apresentação executiva e pitch técnico.
- **`dashboard_sc_disque100_folium.html`**: Mapa interativo com focos penais e unidades PCI-SC.
- **`dashboard_executivo_grupos_sc.html`**: Painel comparativo por grupo vulnerável.

---

## 📁 Estrutura do Projeto

```text
desafio-02-disque100-grupo-03/
├── dashboards/      # Mapas e relatórios interativos em HTML (com proxy legado do Streamlit)
├── data/            # Data Lakehouse (Bronze: dados brutos, Prata: tratados, Ouro: DuckDB/SQLite)
├── notebooks/       # Jupyter Notebook com análise exploratória completa
├── scripts/         # Pipelines ETL de ingestão, triagem penal e agregação
└── streamlit_app/   # Aplicação Streamlit modular e otimizada (components, views, utils)
```


---

## 📊 Consulta Rápida ao Banco (DuckDB)

```python
import duckdb

con = duckdb.connect("data/database/sc_disque100_analitico.duckdb", read_only=True)
print(con.execute("SHOW TABLES").fetchall())
```

---

## 🏛️ Fontes de Dados
- **MDHC / ONDH**: Microdados federais abertos do Disque 100 (2011–2026).
- **IBGE**: População residente oficial do Censo 2022 e limites municipais.
- **Polícia Científica de SC (PCI-SC)**: Unidades regionais e núcleos periciais.
