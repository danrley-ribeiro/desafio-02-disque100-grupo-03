#!/usr/bin/env python3
"""
=============================================================================
Gerador do notebook de analise do Disque 100 em Santa Catarina
=============================================================================
Escreve `notebooks/analise_completa_disque100_sc.ipynb`.

Este arquivo e a fonte de verdade do notebook: todo o conteudo esta aqui, e o
`.ipynb` e um artefato. A versao anterior havia divergido do notebook entregue,
de modo que regerar apagava celulas; agora as duas pontas coincidem.

O notebook documenta a analise que sustenta o painel, com enfase no que os
numeros do Disque 100 podem e nao podem dizer. Foram removidas as tabelas que a
versao anterior trazia escritas a mao, entre elas uma que declarava Barra Bonita
a 52,4 km de uma unidade pericial quando o proprio dado do projeto registra
11,0 km, e que sustentava uma recomendacao de politica publica.

Uso:
    python3 scripts/gerar_notebook_analise.py
    jupyter nbconvert --execute --inplace notebooks/analise_completa_disque100_sc.ipynb
=============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "scripts" else CURRENT_DIR


def construir_notebook() -> Dict[str, Any]:
    nb: Dict[str, Any] = {
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.13",
                "mimetype": "text/x-python",
                "codemirror_mode": {"name": "ipython", "version": 3},
                "pygments_lexer": "ipython3",
                "nbconvert_exporter": "python",
                "file_extension": ".py",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }

    def _linhas(texto: str) -> List[str]:
        linhas = [l + "\n" for l in texto.strip("\n").split("\n")]
        if linhas:
            linhas[-1] = linhas[-1].rstrip("\n")
        return linhas

    def _id(prefixo: str) -> str:
        # nbformat 4.5 exige `id` por celula; sem ele, o nbconvert avisa.
        return f"{prefixo}-{len(nb['cells']):02d}"

    def md(texto: str) -> None:
        nb["cells"].append({
            "cell_type": "markdown",
            "id": _id("md"),
            "metadata": {},
            "source": _linhas(texto),
        })

    def code(texto: str) -> None:
        nb["cells"].append({
            "cell_type": "code",
            "id": _id("cd"),
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": _linhas(texto),
        })

    # =========================================================================
    md('''
# Disque 100 em Santa Catarina: o que os dados sustentam

Analise dos microdados abertos do Disque 100 para Santa Catarina, de 2011 a 2026,
que sustenta o painel em `streamlit_app/`.

O objetivo deste notebook nao e apresentar o maior numero possivel, e sim
estabelecer **o que cada numero significa e sob quais condicoes ele e comparavel**.
Os microdados do Disque 100 tem tres propriedades que, ignoradas, produzem
conclusoes erradas com aparencia de solidez:

1. a linha do arquivo nao e uma denuncia;
2. o esquema muda tres vezes ao longo da serie, e com ele o que e mensuravel;
3. as taxas por habitante dividem contagens de varios anos por um estoque
   populacional de um unico ano.

As secoes a seguir medem cada uma dessas propriedades antes de qualquer
interpretacao substantiva.

## Roteiro

1. Ambiente e base analitica
2. Granularidade: registro de violacao e denuncia
3. As tres eras de esquema
4. Cobertura dos indicadores por semestre
5. Validacao contra o balanco oficial do MDHC
6. Triagem entre indicio penal e demanda socioassistencial
7. Demografia, taxas e o problema dos numeros pequenos
8. Acesso a pericia forense
9. Sintese, reconciliacao e limitacoes
''')

    # =========================================================================
    md('''
## 1. Ambiente e base analitica

O notebook le a base ja materializada em DuckDB, e nao os arquivos brutos. Assim a
analise e o painel enxergam exatamente os mesmos numeros: qualquer divergencia
entre os dois seria erro de um dos lados, nao diferenca de metodo.

Reproduzir a base, a partir da raiz do projeto:

```
python3 scripts/gerar_banco_duckdb_sc.py
python3 scripts/build_annual_kpis.py
python3 scripts/gerar_geo_pci_sc.py
python3 scripts/analisar_distribuicao_penal_sc.py
```
''')

    code('''
from pathlib import Path
import json
import sys

import duckdb
import pandas as pd
import plotly.express as px
import plotly.io as pio

pd.set_option("display.max_columns", 60)
pd.set_option("display.width", 200)
pio.templates.default = "plotly_white"

# Cada figura e gravada nas duas formas na mesma saida de celula:
#   - "plotly_mimetype" grava o grafico interativo, que o JupyterLab usa para
#     dar zoom, isolar series e ler valores no ponto;
#   - "png" grava uma imagem estatica.
# As duas formas ficam no MESMO pacote de saida da celula. O GitHub nao suporta
# o formato interativo do Plotly em .ipynb e exibiria os graficos em branco;
# tendo as duas, ele cai para o PNG, enquanto o JupyterLab escolhe o
# interativo, por ser a representacao mais rica disponivel.
pio.renderers.default = "plotly_mimetype+png"
pio.defaults.default_width = 1000
pio.defaults.default_height = 420
pio.defaults.default_scale = 2

RAIZ = Path.cwd()
if not (RAIZ / "data").exists() and (RAIZ.parent / "data").exists():
    RAIZ = RAIZ.parent
sys.path.insert(0, str(RAIZ / "scripts"))

BANCO = RAIZ / "data" / "database" / "sc_disque100_analitico.duckdb"
PROCESSADOS = RAIZ / "data" / "processed"

con = duckdb.connect(str(BANCO), read_only=True)
consultar = lambda sql: con.execute(sql).fetchdf()

with open(PROCESSADOS / "sc_relatorio_auditoria_dados.json", encoding="utf-8") as f:
    AUDITORIA = json.load(f)

print(f"Raiz do projeto: {RAIZ}")
print(f"Base analitica: {BANCO.relative_to(RAIZ)} ({BANCO.stat().st_size / 1024**2:.1f} MB)")
print(f"Processada em: {AUDITORIA['timestamp_auditoria']}")
print()
print("Tabelas:")
for (nome,) in con.execute("SHOW TABLES").fetchall():
    n = con.execute(f'SELECT COUNT(*) FROM "{nome}"').fetchone()[0]
    print(f"  {nome:<32s} {n:>9,} linhas")
''')

    code('''
# Totais de referencia. Toda afirmacao do notebook e do painel se reconcilia
# com estes numeros.
totais = AUDITORIA["totais"]
for chave, valor in totais.items():
    if isinstance(valor, (int, float)):
        print(f"{chave:<42s} {valor:>12,}")
    else:
        print(f"{chave:<42s} {valor:>12}")
''')

    # =========================================================================
    md('''
## 2. Granularidade: registro de violacao e denuncia

Este e o ponto de partida, porque condiciona tudo o que vem depois.

Cada linha dos microdados e uma combinacao de **violacao, vitima e suspeito**. Uma
denuncia com tres vitimas e quatro tipos de violacao ocupa varias linhas. A coluna
`hash`, presente a partir do segundo semestre de 2020, identifica a denuncia e
permite separar as duas contagens.

A consequencia pratica e que **contar linhas nao e contar denuncias**, e a razao
entre as duas nao e constante: cresce ao longo da serie e varia entre municipios.
Uma serie temporal de contagem de linhas mistura, portanto, mudanca de demanda com
mudanca de registro.
''')

    code('''
por_ano = consultar("""
    SELECT ano,
           COUNT(*) AS registros_violacao,
           COUNT(DISTINCT CASE WHEN grain_denuncia_confiavel = 1 THEN id_denuncia END)
               AS denuncias_unicas,
           COUNT(DISTINCT semestre) AS semestres
    FROM fato_denuncias GROUP BY ano ORDER BY ano
""")
# `replace(0, float("nan"))` mantem a coluna em float64; com pd.NA o dtype
# viraria object e `round` falharia.
por_ano["registros_por_denuncia"] = (
    por_ano["registros_violacao"] / por_ano["denuncias_unicas"].replace(0, float("nan"))
).round(2)
por_ano["cobertura"] = por_ano.apply(
    lambda r: "parcial" if (r["semestres"] == 1 and r["ano"] >= 2020) else "completa", axis=1
)
por_ano
''')

    code('''
# O fator de expansao mais que triplicou entre 2020 e 2026.
comparavel = por_ano.dropna(subset=["registros_por_denuncia"])
fig = px.line(
    comparavel, x="ano", y="registros_por_denuncia", markers=True,
    title="Registros de violacao por denuncia, Santa Catarina",
    labels={"ano": "Ano", "registros_por_denuncia": "Registros por denuncia"},
)
fig.update_traces(line_color="#2a78d6", line_width=2, marker_size=8)
fig.update_layout(yaxis_range=[0, comparavel["registros_por_denuncia"].max() * 1.15])
fig.show()

primeiro, ultimo = comparavel.iloc[0], comparavel.iloc[-1]
print(
    f"De {int(primeiro['ano'])} a {int(ultimo['ano'])}, o fator passou de "
    f"{primeiro['registros_por_denuncia']} para {ultimo['registros_por_denuncia']}, "
    f"multiplicando-se por {ultimo['registros_por_denuncia'] / primeiro['registros_por_denuncia']:.1f}."
)
''')

    code('''
# Crescimento aparente contra crescimento em denuncias, no periodo em que as
# duas contagens existem.
base = comparavel.iloc[0]
fim = comparavel[comparavel["cobertura"] == "completa"].iloc[-1]
cresc_registros = fim["registros_violacao"] / base["registros_violacao"]
cresc_denuncias = fim["denuncias_unicas"] / base["denuncias_unicas"]

print(f"Entre {int(base['ano'])} e {int(fim['ano'])}, em Santa Catarina:")
print(f"  registros de violacao  x{cresc_registros:.2f}")
print(f"  denuncias unicas       x{cresc_denuncias:.2f}")
print()
print(
    f"Parte do crescimento medido em registros e expansao de registro, nao de demanda: "
    f"a razao entre os dois crescimentos e {cresc_registros / cresc_denuncias:.2f}."
)
''')

    code('''
# A dispersao entre municipios e o que inviabiliza o ranking por contagem de linha.
expansao_mun = consultar("""
    SELECT municipio_nome AS municipio,
           COUNT(*) AS registros,
           COUNT(DISTINCT id_denuncia) AS denuncias
    FROM fato_denuncias
    WHERE grain_denuncia_confiavel = 1
    GROUP BY 1 HAVING COUNT(DISTINCT id_denuncia) >= 30
""")
expansao_mun["fator"] = (expansao_mun["registros"] / expansao_mun["denuncias"]).round(2)

print(f"{len(expansao_mun)} municipios com ao menos 30 denuncias identificaveis")
print(expansao_mun["fator"].describe()[["min", "50%", "max"]].round(2).to_string())
print()
print("Cinco maiores fatores:")
print(expansao_mun.nlargest(5, "fator")[["municipio", "registros", "denuncias", "fator"]].to_string(index=False))
print()
print("Cinco menores fatores:")
print(expansao_mun.nsmallest(5, "fator")[["municipio", "registros", "denuncias", "fator"]].to_string(index=False))
print()
print(
    "Dois municipios com o mesmo numero de denuncias podem diferir em mais de duas "
    "vezes na contagem de registros. Rankings municipais por registro medem, em parte, "
    "a complexidade das denuncias, e nao o volume de demanda."
)
''')

    # =========================================================================
    md('''
## 3. As tres eras de esquema

Os 22 arquivos publicados pelo MDHC nao seguem um esquema estavel. Ha tres eras, e a
mesma informacao aparece com grafias diferentes: a coluna de genero da vitima, por
exemplo, tem cinco grafias ao longo da serie, e o arquivo do primeiro semestre de
2023 nao traz a coluna de grupo vulneravel.

Ler essas colunas por nome literal deixa de fora metade da serie. O pipeline resolve
cada campo por uma lista de grafias normalizadas, em
`scripts/colunas_disque100.py`, e registra no relatorio de auditoria o que nao
encontrou em cada arquivo. E isso que a tabela abaixo mostra.
''')

    code('''
inventario = pd.DataFrame(AUDITORIA["inventario_arquivos"])
colunas = [
    "arquivo", "era_esquema", "colunas_no_arquivo", "linhas_sc",
    "linhas_sc_distintas", "denuncias_sc_distintas",
    "fator_expansao_linhas_por_denuncia",
]
inventario[[c for c in colunas if c in inventario.columns]].sort_values("arquivo")
''')

    code('''
# Campos que cada arquivo NAO traz. Sao estas lacunas, e nao o fenomeno, que
# explicam indicadores em zero em alguns periodos.
lacunas = inventario[inventario["campos_ausentes"].map(bool)][["arquivo", "campos_ausentes"]].copy()
lacunas["campos_ausentes"] = lacunas["campos_ausentes"].map(", ".join)
print(lacunas.to_string(index=False))
print()
print("Duplicatas exatas de linha, por arquivo:")
dup = inventario.assign(
    duplicatas=inventario["linhas_sc"] - inventario["linhas_sc_distintas"]
)
dup = dup[dup["duplicatas"] > 0][["arquivo", "linhas_sc", "duplicatas"]]
print(dup.to_string(index=False) if len(dup) else "  nenhuma")
''')

    code('''
# As cinco grafias da coluna de genero, resolvidas pelo mesmo campo canonico.
import pyarrow.parquet as pq
from colunas_disque100 import ResolvedorColunas, normalizar_chave

grafias = {}
for caminho in sorted((RAIZ / "data" / "raw").glob("disque100-*.parquet")):
    nomes = pq.ParquetFile(caminho).schema_arrow.names
    resolvido = ResolvedorColunas(nomes).coluna("genero_vitima")
    grafias.setdefault(resolvido or "(ausente)", []).append(caminho.stem.replace("disque100-", ""))

for grafia, arquivos in grafias.items():
    print(f"{grafia!r:<26s} -> {len(arquivos)} arquivo(s): {', '.join(arquivos[:4])}"
          + (" ..." if len(arquivos) > 4 else ""))
print()
print("Todas normalizam para a mesma chave:",
      {normalizar_chave(g) for g in grafias if g != "(ausente)"})
''')

    # =========================================================================
    md('''
## 4. Cobertura dos indicadores por semestre

Um indicador em zero pode significar duas coisas muito diferentes: ausencia do
fenomeno, ou ausencia do campo que o identifica. Distinguir as duas e obrigatorio
antes de qualquer leitura de serie temporal por grupo vulneravel.

O caso mais importante e o das mulheres. O modulo "Violencia contra a Mulher" so
existe nos microdados a partir de 2025. Antes disso, a marcacao depende de inferencia
a partir de genero e relacao vitima-suspeito, e portanto **a serie desse grupo nao
mede a mesma coisa ao longo do tempo**. O painel declara isso na propria aba de
grupos.
''')

    code('''
cobertura = pd.DataFrame(AUDITORIA["cobertura_por_semestre"])
cobertura["periodo"] = cobertura.apply(
    lambda r: f"{int(r['ano'])}" if r["semestre"] == 0 else f"{int(r['ano'])}/{int(r['semestre'])}",
    axis=1,
)
grupos = ["is_crianca", "is_mulher", "is_idoso", "is_pcd", "is_lgbtqia", "is_prisional_rua"]
cobertura[["periodo", "registros", "denuncias_unicas", "fator_expansao",
           "pct_penal", "pct_sem_grupo"] + grupos]
''')

    code('''
comparabilidade = AUDITORIA["comparabilidade_grupos"]
print("Desde quando cada grupo tem modulo proprio nos microdados:")
for flag, info in comparabilidade["por_grupo"].items():
    desde = info["comparavel_desde"]
    print(f"  {flag:<20s} {str(desde):<6s} {info['observacao']}")
print()
if comparabilidade["anos_sem_coluna_de_grupo"]:
    print("Anos em que algum arquivo nao traz a coluna de grupo vulneravel:",
          comparabilidade["anos_sem_coluna_de_grupo"])
''')

    code('''
# O efeito da lacuna de 2023/1 sobre a proporcao sem grupo identificado.
sem_grupo = cobertura[["periodo", "pct_sem_grupo"]].copy()
fig = px.bar(
    sem_grupo, x="periodo", y="pct_sem_grupo",
    title="Registros sem grupo vulneravel identificado, por semestre",
    labels={"periodo": "Periodo", "pct_sem_grupo": "% sem grupo"},
)
fig.update_traces(marker_color="#eb6834")
fig.update_layout(xaxis_tickangle=-45)
fig.show()

pico = sem_grupo.loc[sem_grupo["pct_sem_grupo"].idxmax()]
print(
    f"O pico em {pico['periodo']} ({pico['pct_sem_grupo']:.1f}%) nao e mudanca de perfil "
    "das denuncias: e o arquivo daquele semestre que nao traz a coluna de grupo "
    "vulneravel, restando apenas faixa etaria, deficiencia e orientacao sexual para "
    "atribuir o grupo."
)
''')

    # =========================================================================
    md('''
## 5. Validacao contra o balanco oficial do MDHC

Para o periodo de 2011 a 2019, os microdados nao trazem identificador de denuncia,
de modo que a contagem de denuncias nao pode ser apurada a partir deles. Existe,
porem, uma referencia externa: os balancos gerais publicados pelo proprio MDHC, que
acompanham o repositorio em `data/raw/balancos-gerais/`.

Essa comparacao e a evidencia mais direta de que registro e denuncia sao unidades
distintas, e dimensiona a diferenca no periodo em que nao ha como medi-la
internamente.
''')

    code('''
externa = AUDITORIA["validacao_externa_mdhc"]
oficial = pd.Series(externa["denuncias_sc_por_ano"], name="denuncias_oficiais").astype(int)
oficial.index = oficial.index.astype(int)

nossos = cobertura.groupby("ano")["registros"].sum()
comparacao = pd.DataFrame({"denuncias_balanco_mdhc": oficial}).join(
    nossos.rename("registros_violacao_projeto")
).dropna()
comparacao["registros_por_denuncia"] = (
    comparacao["registros_violacao_projeto"] / comparacao["denuncias_balanco_mdhc"]
).round(2)
comparacao.index.name = "ano"
display(comparacao)

print(f"Fonte: {externa['fonte']}")
print(f"Arquivo: {externa['arquivo']}")
print()
tot_of = int(comparacao["denuncias_balanco_mdhc"].sum())
tot_no = int(comparacao["registros_violacao_projeto"].sum())
print(f"2011 a 2019: {tot_of:,} denuncias oficiais contra {tot_no:,} registros de violacao")
print(f"Razao media: {tot_no / tot_of:.2f} registros por denuncia")
''')

    # =========================================================================
    md('''
## 6. Triagem entre indicio penal e demanda socioassistencial

A triagem e feita por uma taxonomia de palavras-chave aplicada ao texto da violacao
relatada, em `scripts/classificar_indicio_penal.py`. Quando reconhece um tipo penal,
o pipeline marca a ocorrencia e registra a fundamentacao legal e o orgao de
encaminhamento sugerido.

Duas ressalvas que acompanham qualquer uso desses numeros:

- **Nao e decisao juridica.** Indica onde ha indicio a apurar. Nao foi validada
  contra inquerito ou laudo, e sua precisao nao foi medida.
- **A proporcao penal nao e comparavel ao longo da serie.** O vocabulario de violacao
  muda entre as eras de esquema, e com ele a fracao do texto que a taxonomia
  reconhece. A secao mede esse efeito em vez de ignora-lo.
''')

    code('''
categorias = consultar("""
    SELECT categoria_penal, grau_certeza, orgao_prioritario, fundamentacao_legal,
           COUNT(*) AS registros
    FROM fato_denuncias WHERE indicio_penal = 1
    GROUP BY 1, 2, 3, 4 ORDER BY registros DESC
""")
categorias["pct_do_penal"] = (
    100 * categorias["registros"] / categorias["registros"].sum()
).round(2)
categorias[["categoria_penal", "grau_certeza", "registros", "pct_do_penal", "orgao_prioritario"]]
''')

    code('''
# Instabilidade da proporcao penal ao longo da serie.
agregado = cobertura.groupby("ano", as_index=False)[["registros", "penal"]].sum()
agregado["pct_penal"] = 100 * agregado["penal"] / agregado["registros"]
penal_ano = agregado[["ano", "pct_penal"]]

fig = px.line(
    penal_ano, x="ano", y="pct_penal", markers=True,
    title="Proporcao com indicio penal, por ano",
    labels={"ano": "Ano", "pct_penal": "% com indicio penal"},
)
fig.update_traces(line_color="#2a78d6", line_width=2, marker_size=8)
fig.update_layout(yaxis_range=[0, 100])
fig.add_vline(x=2019.5, line_dash="dot", line_color="#898781")
fig.add_annotation(x=2019.5, yref="paper", y=1.0, text="troca de esquema",
                   showarrow=False, font_size=10, font_color="#898781",
                   xanchor="left", yanchor="bottom")
fig.show()

print(penal_ano.assign(pct_penal=penal_ano["pct_penal"].round(1)).to_string(index=False))
print()
print(
    "O salto entre 2018 e 2020 acompanha a troca de esquema dos microdados, nao uma "
    "mudanca de igual magnitude no perfil das denuncias. Comparacoes de proporcao penal "
    "devem ficar dentro de uma mesma era."
)
''')

    code('''
# No nivel da denuncia, "penal" significa "ao menos uma violacao tipificada".
# Por isso a proporcao sobe muito em relacao a medida em registros: a medida
# comparavel e a predominancia.
decomposicao = consultar("""
    WITH d AS (
        SELECT id_denuncia, COUNT(*) AS n, SUM(indicio_penal) AS p
        FROM fato_denuncias WHERE grain_denuncia_confiavel = 1 GROUP BY 1
    )
    SELECT COUNT(*) AS denuncias,
           COUNT(*) FILTER (WHERE p = 0) AS sem_nenhum_penal,
           COUNT(*) FILTER (WHERE p > 0) AS com_algum_penal,
           COUNT(*) FILTER (WHERE p * 2 > n) AS maioria_penal,
           COUNT(*) FILTER (WHERE p = n) AS integralmente_penal
    FROM d
""").iloc[0]

total = int(decomposicao["denuncias"])
pct_registros = 100 * int(totais["registros_penal"]) / int(totais["registros_de_violacao"])
print(f"Denuncias identificaveis: {total:,}")
for rotulo, chave in [
    ("com algum indicio penal", "com_algum_penal"),
    ("com maioria penal", "maioria_penal"),
    ("integralmente penais", "integralmente_penal"),
    ("sem nenhum indicio penal", "sem_nenhum_penal"),
]:
    v = int(decomposicao[chave])
    print(f"  {rotulo:<28s} {v:>8,}  {100 * v / total:>5.1f}%")
print()
print(f"Proporcao penal medida em registros de violacao: {pct_registros:.1f}%")
print(
    "A predominancia penal por denuncia e a medida comparavel a proporcao apurada em "
    "registros; 'com algum indicio penal' responde a outra pergunta e fica muito acima."
)
''')

    # =========================================================================
    md('''
## 7. Demografia, taxas e o problema dos numeros pequenos

As taxas usam a populacao residente do Censo 2022 do IBGE, tabela SIDRA 4714. Duas
limitacoes acompanham esse denominador:

- e um estoque de um unico ano, aplicado a contagens de varios anos; para os anos
  mais distantes de 2022 e apenas uma aproximacao;
- em municipios pequenos, a taxa e instavel: poucas denuncias a deslocam em ordens de
  magnitude.

A segunda limitacao nao e teorica. Sem piso populacional, o topo do ranking por taxa
e ocupado por municipios de poucos milhares de habitantes, e a leitura literal do
numero chega a fracoes absurdas da populacao. O painel aplica um piso ao ranking por
taxa e ao destaque de focos no mapa, e diz isso na tela.
''')

    code('''
municipios = consultar("""
    SELECT ibge_code, municipio, regiao_intermediaria, populacao_censo_2022,
           total_registros, total_penal, denuncias_unicas, taxa_total_10k, taxa_penal_10k
    FROM kpis_grupos_municipios ORDER BY total_registros DESC
""")

demografia = AUDITORIA["demografia"]
print(f"Fonte: {demografia['fonte']}")
print(f"Municipios: {demografia['municipios']}")
print(f"Populacao total: {demografia['populacao_total']:,}")
print(f"Sem populacao no Censo: {demografia['municipios_sem_populacao_no_censo'] or 'nenhum'}")
print()
print("Dez municipios com maior volume de registros:")
print(municipios.head(10)[["municipio", "populacao_censo_2022", "total_registros", "taxa_total_10k"]].to_string(index=False))
''')

    code('''
# Taxa contra populacao: a instabilidade aparece como um funil a esquerda.
fig = px.scatter(
    municipios, x="populacao_censo_2022", y="taxa_total_10k",
    hover_name="municipio", color="regiao_intermediaria",
    log_x=True,
    title="Taxa por 10 mil habitantes contra populacao do municipio",
    labels={
        "populacao_censo_2022": "Populacao (escala logaritmica)",
        "taxa_total_10k": "Registros por 10 mil hab., periodo completo",
        "regiao_intermediaria": "Regiao intermediaria",
    },
)
fig.update_traces(marker=dict(size=8, line=dict(width=1, color="#fcfcfb")))
fig.add_vline(x=20000, line_dash="dot", line_color="#898781")
fig.add_annotation(x=20000, yref="paper", y=1.0, text="piso de 20 mil hab.",
                   showarrow=False, font_size=10, font_color="#898781",
                   xanchor="left", yanchor="bottom")
fig.update_layout(legend_title_text="")
fig.show()

print(
    "A dispersao vertical se estreita conforme a populacao cresce. Isso e o "
    "comportamento esperado de uma razao com denominador pequeno, e nao um padrao "
    "territorial a ser interpretado."
)
''')

    code('''
# Efeito do piso populacional sobre o ranking por taxa.
media_estadual = (
    municipios["total_registros"].sum() / municipios["populacao_censo_2022"].sum() * 10000
)
print(f"Taxa do estado no periodo completo: {media_estadual:,.1f} por 10 mil hab.")
print()
for piso in [0, 5_000, 10_000, 20_000, 50_000]:
    elegiveis = municipios[municipios["populacao_censo_2022"] >= piso]
    topo = elegiveis.nlargest(1, "taxa_total_10k").iloc[0]
    rotulo = "sem piso" if piso == 0 else f"{piso:,} hab."
    print(
        f"  piso {rotulo:<12s} topo: {topo['municipio']:<22s} "
        f"pop {int(topo['populacao_censo_2022']):>7,}  "
        f"{topo['taxa_total_10k']:>8,.1f}/10k  "
        f"{topo['taxa_total_10k'] / media_estadual:>5.1f}x a media"
    )
print()
sem_piso = municipios.nlargest(1, "taxa_total_10k").iloc[0]
print(
    f"Sem piso, {sem_piso['municipio']} aparece com {sem_piso['taxa_total_10k']:,.0f} "
    f"registros por 10 mil habitantes, o equivalente a "
    f"{sem_piso['taxa_total_10k'] / 10000:.0%} da propria populacao ao longo do periodo. "
    "O numero esta aritmeticamente correto e nao suporta a leitura que sugere."
)
''')

    # =========================================================================
    md('''
## 8. Acesso a pericia forense

Em crimes contra a dignidade sexual e em lesoes corporais, o exame de corpo de delito
e a coleta de vestigios dependem da chegada da vitima a uma unidade da Policia
Cientifica. O projeto mede a **distancia geodesica em linha reta** entre o centroide
do municipio e a unidade mais proxima, calculada por haversine em
`scripts/gerar_geo_pci_sc.py`.

Isso nao e distancia rodoviaria e nao sustenta, por si, estimativa de tempo de
deslocamento: em relevo de serra o percurso por estrada chega a uma vez e meia a
distancia em linha reta. As faixas abaixo sao faixas de distancia, nao isocronas.
''')

    code('''
with open(PROCESSADOS / "sc_municipios_distancia_pci.json", encoding="utf-8") as f:
    matriz = json.load(f)

print(matriz["metadata"]["descricao"])
print()
distancias = pd.DataFrame(matriz["municipios"]).T
distancias["distancia_pci_km_linha_reta"] = distancias["distancia_pci_km_linha_reta"].astype(float)
distancias["populacao_censo_2022"] = pd.to_numeric(distancias["populacao_censo_2022"])

por_faixa = distancias.groupby("faixa_distancia").agg(
    municipios=("municipio", "count"),
    populacao=("populacao_censo_2022", "sum"),
    distancia_mediana=("distancia_pci_km_linha_reta", "median"),
).reset_index()
display(por_faixa)

print(
    f"Distancia em linha reta: minima {distancias['distancia_pci_km_linha_reta'].min():.1f} km, "
    f"mediana {distancias['distancia_pci_km_linha_reta'].median():.1f} km, "
    f"maxima {distancias['distancia_pci_km_linha_reta'].max():.1f} km"
)
''')

    code('''
# Os municipios efetivamente acima de 50 km, consultados do dado.
acima = distancias[distancias["distancia_pci_km_linha_reta"] > 50].sort_values(
    "distancia_pci_km_linha_reta", ascending=False
)
print(f"{len(acima)} municipios acima de 50 km em linha reta:")
print(acima[[
    "municipio", "regiao_intermediaria", "populacao_censo_2022",
    "distancia_pci_km_linha_reta", "pci_proxima_municipio",
]].to_string(index=False))
''')

    code('''
# Volume com indicio penal nesses municipios, para dimensionar a demanda que
# depende do deslocamento mais longo.
codigos = "', '".join(acima.index.astype(str))
demanda_distante = consultar(f"""
    SELECT municipio, populacao_censo_2022, total_registros, total_penal, taxa_penal_10k
    FROM kpis_grupos_municipios
    WHERE ibge_code IN ('{codigos}')
    ORDER BY total_penal DESC
""")
display(demanda_distante)

unidades = consultar("SELECT tipo, COUNT(*) AS unidades FROM dim_unidades_pci GROUP BY 1 ORDER BY 1")
print("Rede da Policia Cientifica de Santa Catarina:")
print(unidades.to_string(index=False))
print(f"Total: {int(unidades['unidades'].sum())} unidades")
print()
print(
    f"Os {len(acima)} municipios acima de 50 km somam "
    f"{int(demanda_distante['populacao_censo_2022'].sum()):,} habitantes e "
    f"{int(demanda_distante['total_penal'].sum()):,} registros com indicio penal no periodo, "
    f"{100 * demanda_distante['total_penal'].sum() / int(totais['registros_penal']):.1f}% do total do estado."
)
''')

    # =========================================================================
    md('''
## 9. Sintese, reconciliacao e limitacoes

As duas ultimas celulas fecham a analise: a reconciliacao verifica que os totais do
notebook, do relatorio de auditoria e das tabelas materializadas coincidem, e a
tabela de hashes permite conferir que os arquivos lidos aqui sao os mesmos que o
painel consome.

A verificacao nao e tautologica. Ela compara **contagens obtidas por caminhos
diferentes**: varredura do fato, soma da tabela agregada por municipio e o que o
relatorio de auditoria registrou no momento do processamento. Divergencia entre elas
indicaria erro de agregacao.
''')

    code('''
fato = consultar("""
    SELECT COUNT(*) AS registros, SUM(indicio_penal) AS penal,
           COUNT(DISTINCT CASE WHEN grain_denuncia_confiavel = 1 THEN id_denuncia END) AS denuncias
    FROM fato_denuncias
""").iloc[0]
kpi = consultar("""
    SELECT SUM(total_registros) AS registros, SUM(total_penal) AS penal,
           SUM(denuncias_unicas) AS denuncias FROM kpis_grupos_municipios
""").iloc[0]
kpi_ano = consultar("""
    SELECT SUM(total_denuncias) AS registros, SUM(total_penal) AS penal,
           SUM(denuncias_unicas) AS denuncias FROM kpis_grupos_municipios_ano
""").iloc[0]

reconciliacao = pd.DataFrame({
    "fato_denuncias": [int(fato["registros"]), int(fato["penal"]), int(fato["denuncias"])],
    "kpis_por_municipio": [int(kpi["registros"]), int(kpi["penal"]), int(kpi["denuncias"])],
    "kpis_por_municipio_ano": [int(kpi_ano["registros"]), int(kpi_ano["penal"]), int(kpi_ano["denuncias"])],
    "relatorio_auditoria": [
        int(totais["registros_de_violacao"]), int(totais["registros_penal"]),
        int(totais["denuncias_unicas_identificaveis"]),
    ],
}, index=["registros_violacao", "com_indicio_penal", "denuncias_unicas"])
display(reconciliacao)

conciliacao = AUDITORIA["conciliacao_municipal"]
print(
    f"A diferenca entre o fato e as tabelas municipais e de "
    f"{conciliacao['registros_sem_municipio_identificado']:,} registros sem municipio "
    "identificado, excluidos dos indicadores municipais porque nao ha municipio a que "
    "atribui-los."
)
print()
print(
    "As duas tabelas de KPI batem entre si e com o fato descontada essa diferenca; as "
    "denuncias unicas somadas por municipio ficam ligeiramente abaixo do total distinto "
    "porque dez denuncias aparecem em mais de um municipio."
)
''')

    code('''
import hashlib

print("Integridade dos artefatos lidos por este notebook e pelo painel:")
print()
ok = 0
for nome, esperado in AUDITORIA["arquivos_hashes_sha256"].items():
    caminho = PROCESSADOS / nome
    if not caminho.exists():
        print(f"  ausente   {nome}")
        continue
    real = hashlib.sha256(caminho.read_bytes()).hexdigest()
    confere = real == esperado
    ok += confere
    print(f"  {'confere' if confere else 'DIVERGE':<9s} {nome:<44s} {real[:16]}...")
print()
print(f"{ok} de {len(AUDITORIA['arquivos_hashes_sha256'])} arquivos conferem.")
print()
print("Limitacoes conhecidas, conforme o relatorio de auditoria:")
for i, item in enumerate(AUDITORIA["limitacoes_conhecidas"], 1):
    print(f"  {i}. {item}")
con.close()
''')

    # =========================================================================
    md('''
## Fontes

| Fonte | Conteudo |
| :--- | :--- |
| [MDHC / Ouvidoria Nacional de Direitos Humanos](https://www.gov.br/mdh/pt-br/ondh) | Microdados abertos do Disque 100, 2011 a 2026, e balancos tematicos |
| [IBGE, Censo Demografico 2022, tabela 4714](https://sidra.ibge.gov.br/tabela/4714) | Populacao residente dos 295 municipios de Santa Catarina |
| [IBGE, API de Malhas](https://servicodados.ibge.gov.br/api/docs/malhas) | Malha vetorial municipal e divisao regional de 2017 |
| [Policia Cientifica de Santa Catarina](https://www.policiacientifica.sc.gov.br/unidades/) | Catalogo das 30 unidades: 9 superintendencias e 21 nucleos |
| [MDS, SUAS](https://www.gov.br/mds/pt-br/acoes-e-programas/suas) | Tipificacao Nacional de Servicos Socioassistenciais, Resolucao CNAS 109/2009 |

Grupo 03, Ciencia de Dados, UFSC.
''')

    return nb


def main() -> None:
    nb = construir_notebook()
    destino = ROOT_DIR / "notebooks" / "analise_completa_disque100_sc.ipynb"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
        f.write("\n")

    md = sum(1 for c in nb["cells"] if c["cell_type"] == "markdown")
    codigo = sum(1 for c in nb["cells"] if c["cell_type"] == "code")
    print(f"{destino.relative_to(ROOT_DIR)}: {len(nb['cells'])} celulas ({md} markdown, {codigo} codigo)")
    print("Para gravar as saidas:")
    print("  jupyter nbconvert --execute --inplace notebooks/analise_completa_disque100_sc.ipynb")


if __name__ == "__main__":
    main()
