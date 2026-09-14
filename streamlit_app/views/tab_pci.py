"""
=============================================================================
Aba Capacidade forense: acesso a Policia Cientifica de Santa Catarina
=============================================================================
Duas correcoes de substancia em relacao a versao anterior:

  1. O catalogo das unidades saia inteiramente em branco. A dimensao era
     construida lendo chaves que nao existem no JSON raspado do portal
     oficial, de modo que nome, sigla, tipo e jurisdicao vinham vazios e as
     coordenadas vinham zeradas. Agora a aba mostra unidade, tipo, sede,
     endereco, telefone, horario e servicos disponiveis.

  2. Os tempos de deslocamento foram removidos. A aba afirmava "atendidos em
     menos de 30 minutos", "de 30 min a 1h" e "deslocamento superior a 1h15",
     sem que exista qualquer coluna de tempo nos dados: a unica medida
     disponivel e a distancia geodesica em linha reta. Quem quiser uma
     estimativa de tempo escolhe a velocidade media, e a premissa fica na tela.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from streamlit_app.config import (
    AJUDA_DISTANCIA,
    FAIXA_COR,
    FAIXA_DISTANTE,
    FAIXA_INTERMEDIARIA,
    FAIXA_PROXIMA,
    FAIXAS_DISTANCIA,
    Filtros,
    UNIDADE_ROTULO,
)
from streamlit_app.utils.charts import ALTURA_BAIXA, barras_horizontais
from streamlit_app.utils.formatters import (
    SEM_DADO,
    formatar_km,
    formatar_numero,
    formatar_taxa,
)

VELOCIDADES = {
    "Não estimar tempo": 0,
    "50 km/h (média rodoviária estadual)": 50,
    "70 km/h (rodovia federal)": 70,
}

# Fator de desvio rodoviario tipico em relevo acidentado. Usado apenas quando o
# usuario pede a estimativa, e sempre declarado na tela.
FATOR_ROTA = 1.4


def render_tab_pci(
    df: pd.DataFrame,
    df_pci: pd.DataFrame,
    filtros: Filtros,
    metadados: Dict[str, Any],
) -> None:
    st.subheader("Acesso à perícia forense")
    st.caption(
        "Em crimes contra a dignidade sexual e em lesões corporais, o exame de corpo de "
        "delito e a coleta de vestígios biológicos dependem da chegada da vítima a uma "
        "unidade da Polícia Científica. A distância abaixo é a medida disponível no "
        "projeto; não há modelo de tempo de deslocamento."
    )

    if "distancia_pci_km" not in df.columns or df["distancia_pci_km"].isna().all():
        st.warning(
            "Matriz de distância não encontrada. Execute "
            "`python3 scripts/gerar_geo_pci_sc.py`."
        )
    else:
        _render_faixas(df, filtros)
        _render_municipios_distantes(df, filtros)

    _render_catalogo(df_pci, metadados)


def _render_faixas(df: pd.DataFrame, filtros: Filtros) -> None:
    com_dado = df.dropna(subset=["distancia_pci_km"])
    if com_dado.empty:
        return

    st.markdown("**Municípios por faixa de distância**")
    st.caption(AJUDA_DISTANCIA)

    contagem = com_dado["faixa_distancia"].value_counts()
    colunas = st.columns(3)
    for coluna, faixa in zip(colunas, FAIXAS_DISTANCIA):
        n = int(contagem.get(faixa, 0))
        pop = int(com_dado[com_dado["faixa_distancia"] == faixa]["populacao_censo_2022"].sum())
        with coluna:
            st.metric(faixa, f"{n} municípios")
            st.caption(f"{formatar_numero(pop)} habitantes")

    velocidade_label = st.selectbox(
        "Estimativa de tempo de deslocamento",
        list(VELOCIDADES.keys()),
        help=(
            "O projeto não tem dado de tempo de viagem. Se você escolher uma velocidade, "
            f"o tempo é estimado como distância em linha reta multiplicada por {FATOR_ROTA} "
            "para aproximar o percurso por estrada, dividida pela velocidade. É uma "
            "aproximação declarada, não uma medição."
        ),
    )
    velocidade = VELOCIDADES[velocidade_label]
    if velocidade:
        maior = com_dado["distancia_pci_km"].max()
        minutos = (maior * FATOR_ROTA / velocidade) * 60
        st.caption(
            f"Premissa: percurso por estrada estimado em {FATOR_ROTA} vezes a distância em "
            f"linha reta, a {velocidade} km/h. Sob essa premissa, o município mais distante "
            f"({formatar_km(maior)} em linha reta) fica a cerca de {minutos:.0f} minutos."
        )


def _render_municipios_distantes(df: pd.DataFrame, filtros: Filtros) -> None:
    unidade = UNIDADE_ROTULO[filtros.unidade_efetiva()]
    distantes = df[df["faixa_distancia"] == FAIXA_DISTANTE].copy()

    st.markdown(f"**Municípios acima de 50 km com maior volume penal**")
    if distantes.empty:
        st.info(
            "Nenhum município do recorte selecionado está acima de 50 km de uma unidade "
            "pericial."
        )
        return

    st.caption(
        f"Ordenados pelo volume de ocorrências com indício penal no período "
        f"{filtros.label_periodo}."
    )
    distantes = distantes.nlargest(min(10, len(distantes)), "valor_penal")

    st.dataframe(
        pd.DataFrame({
            "Município": distantes["municipio"],
            "Região intermediária": distantes["regiao_intermediaria"],
            "População": distantes["populacao_censo_2022"].map(formatar_numero),
            f"Indício penal ({unidade})": distantes["valor_penal"].map(formatar_numero),
            f"Taxa anual {filtros.rotulo_escala}": distantes["taxa_penal"].map(formatar_taxa),
            "Distância em linha reta": distantes["distancia_pci_km"].map(formatar_km),
            "Unidade pericial de referência": distantes["pci_proxima"].fillna(SEM_DADO),
        }),
        hide_index=True,
        width="stretch",
    )

    st.plotly_chart(
        barras_horizontais(
            distantes,
            coluna_categoria="municipio",
            coluna_valor="distancia_pci_km",
            rotulo_valor="Distância em linha reta (km)",
            cor=FAIXA_COR[FAIXA_DISTANTE],
            sufixo_dica=" km",
            colunas_extra={"pci_proxima_municipio": "Unidade mais próxima"},
            altura=ALTURA_BAIXA,
        ),
        width="stretch",
        key="pci_distancia",
    )


def _render_catalogo(df_pci: pd.DataFrame, metadados: Dict[str, Any]) -> None:
    composicao = metadados.get("composicao_pci") or {}
    if composicao:
        resumo = ", ".join(f"{v} {k.lower()}" for k, v in sorted(composicao.items()))
        titulo = f"Catálogo das {metadados.get('unidades_pci', len(df_pci))} unidades ({resumo})"
    else:
        titulo = f"Catálogo das {len(df_pci)} unidades da Polícia Científica"

    with st.expander(titulo):
        if df_pci.empty:
            st.warning("Dimensão de unidades periciais vazia.")
            return

        colunas = {
            "sigla": "Sigla",
            "nome": "Unidade",
            "tipo": "Tipo",
            "municipio": "Sede",
            "endereco": "Endereço",
            "telefone": "Telefone",
            "horario_medicina_legal": "Medicina legal",
            "url_oficial": "Página oficial",
        }
        presentes = {k: v for k, v in colunas.items() if k in df_pci.columns}
        tabela = df_pci[list(presentes.keys())].rename(columns=presentes)

        config = {}
        if "Página oficial" in tabela.columns:
            config["Página oficial"] = st.column_config.LinkColumn(
                "Página oficial", display_text="abrir"
            )
        st.dataframe(
            tabela.sort_values(["Tipo", "Sede"]) if "Tipo" in tabela.columns else tabela,
            hide_index=True,
            width="stretch",
            column_config=config,
        )

        servicos = [c for c in ("tem_medicina_legal", "tem_criminalistica", "tem_identificacao") if c in df_pci.columns]
        if servicos:
            rotulos = {
                "tem_medicina_legal": "Medicina legal (IML, lesão corporal, necropsia)",
                "tem_criminalistica": "Criminalística e perícias forenses",
                "tem_identificacao": "Identificação civil e criminal",
            }
            linhas = [
                f"- {rotulos[c]}: {int(df_pci[c].sum())} de {len(df_pci)} unidades"
                for c in servicos
            ]
            st.caption("Serviços declarados no portal oficial:  \n" + "  \n".join(linhas))
