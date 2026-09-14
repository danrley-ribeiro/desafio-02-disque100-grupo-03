"""
=============================================================================
Aba Metodologia e auditoria
=============================================================================
A versao anterior deste arquivo terminava truncada: calculava os dois hashes
SHA-256 e nunca os renderizava, enquanto a barra lateral anunciava "hashes
auditados". Os campos ricos do relatorio de auditoria tambem nao chegavam a
tela.

Aqui o relatorio e o conteudo da aba: unidade de medida, limitacoes conhecidas,
cobertura por semestre, fator de expansao entre registro e denuncia,
comparacao com o balanco oficial do MDHC, inventario por arquivo e a tabela de
hashes. A fundamentacao legal continua presente, condensada.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from streamlit_app.config import (
    AJUDA_DISTANCIA,
    AJUDA_PENAL,
    AJUDA_SOCIAL,
    AJUDA_TAXA,
    CATEGORICA,
    FONTES_OFICIAIS,
)
from streamlit_app.utils.charts import ALTURA_BAIXA, series_temporal
from streamlit_app.utils.formatters import formatar_numero, formatar_percentual, formatar_taxa


def render_tab_metodologia(auditoria: Dict[str, Any]) -> None:
    st.subheader("Metodologia e auditoria")

    if not auditoria:
        st.warning(
            "Relatório de auditoria não encontrado. Execute "
            "`python3 scripts/gerar_banco_duckdb_sc.py`."
        )
    else:
        _render_unidade(auditoria)
        _render_limitacoes(auditoria)
        _render_validacao_externa(auditoria)
        _render_cobertura(auditoria)
        _render_inventario(auditoria)
        _render_hashes(auditoria)

    _render_triagem()
    _render_fontes()


def _render_unidade(auditoria: Dict[str, Any]) -> None:
    unidade = auditoria.get("unidade_de_medida", {})
    totais = auditoria.get("totais", {})
    conciliacao = auditoria.get("conciliacao_municipal", {})

    st.markdown("### Unidade de medida")
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros de violação", formatar_numero(totais.get("registros_de_violacao")))
    c2.metric("Denúncias únicas apuráveis", formatar_numero(totais.get("denuncias_unicas_identificaveis")))
    registros_id = totais.get("registros_com_denuncia_identificavel")
    denuncias = totais.get("denuncias_unicas_identificaveis")
    if registros_id and denuncias:
        c3.metric("Registros por denúncia", formatar_taxa(registros_id / denuncias))

    st.markdown(
        f"- **Registro de violação**: {unidade.get('registro_de_violacao', '')}\n"
        f"- **Denúncia única**: {unidade.get('denuncia_unica', '')}\n"
        f"- {unidade.get('advertencia', '')}"
    )

    if conciliacao:
        st.caption(
            f"Conciliação: {formatar_numero(conciliacao.get('registros_no_fato'))} registros no "
            f"fato, {formatar_numero(conciliacao.get('registros_atribuidos_a_municipio'))} "
            f"atribuídos a município e "
            f"{formatar_numero(conciliacao.get('registros_sem_municipio_identificado'))} sem "
            "município identificado. " + (conciliacao.get("observacao") or "")
        )

    dispersao = auditoria.get("dispersao_fator_expansao_municipal") or {}
    if dispersao:
        st.caption(
            "Dispersão do fator de expansão entre municípios "
            f"({dispersao.get('criterio')}): de {formatar_taxa(dispersao.get('fator_minimo'))} a "
            f"{formatar_taxa(dispersao.get('fator_maximo'))} registros por denúncia, mediana "
            f"{formatar_taxa(dispersao.get('fator_mediano'))}. É essa dispersão, e não a média, "
            "que impede comparar municípios por contagem de registro."
        )


def _render_limitacoes(auditoria: Dict[str, Any]) -> None:
    limitacoes: List[str] = auditoria.get("limitacoes_conhecidas") or []
    demografia = auditoria.get("demografia") or {}
    pci = auditoria.get("policia_cientifica") or {}
    incompletos = auditoria.get("anos_incompletos") or {}

    st.markdown("### Limitações conhecidas")
    itens = list(limitacoes)
    if demografia.get("limitacao_denominador"):
        itens.append(demografia["limitacao_denominador"])
    if pci.get("limitacao_distancia"):
        itens.append(pci["limitacao_distancia"])
    if incompletos:
        anos = ", ".join(str(a) for a in incompletos)
        itens.append(
            f"Cobertura parcial em {anos}: apenas um semestre de dados. Totais absolutos "
            "desses anos ficam abaixo do patamar real."
        )
    for item in itens:
        st.markdown(f"- {item}")


def _render_validacao_externa(auditoria: Dict[str, Any]) -> None:
    ext = auditoria.get("validacao_externa_mdhc") or {}
    if not ext.get("disponivel"):
        return

    st.markdown("### Validação contra o balanço oficial")
    st.caption(
        f"Fonte: {ext.get('fonte')}. É a única referência independente disponível para "
        "dimensionar a diferença entre denúncia e registro de violação no período em que "
        "os microdados não trazem identificador de denúncia."
    )

    por_ano = ext.get("denuncias_sc_por_ano") or {}
    cobertura = {
        str(c["ano"]): c["registros"]
        for c in (auditoria.get("cobertura_por_semestre") or [])
        if str(c["ano"]) in por_ano
    }
    # Soma por ano, porque a cobertura vem por semestre.
    registros_por_ano: Dict[str, int] = {}
    for c in auditoria.get("cobertura_por_semestre") or []:
        chave = str(c["ano"])
        if chave in por_ano:
            registros_por_ano[chave] = registros_por_ano.get(chave, 0) + int(c["registros"])

    linhas = []
    for ano in sorted(por_ano):
        oficial = por_ano[ano]
        nossos = registros_por_ano.get(ano)
        linhas.append({
            "ano": int(ano),
            "Denúncias (balanço MDHC)": oficial,
            "Registros de violação (este projeto)": nossos,
            "Registros por denúncia": (nossos / oficial) if (nossos and oficial) else None,
        })
    df = pd.DataFrame(linhas)

    st.dataframe(
        pd.DataFrame({
            "Ano": df["ano"],
            "Denúncias (balanço MDHC)": df["Denúncias (balanço MDHC)"].map(formatar_numero),
            "Registros de violação": df["Registros de violação (este projeto)"].map(formatar_numero),
            "Registros por denúncia": df["Registros por denúncia"].map(formatar_taxa),
        }),
        hide_index=True,
        width="stretch",
    )
    total_oficial = ext.get("total_denuncias_sc")
    total_nosso = int(df["Registros de violação (este projeto)"].fillna(0).sum())
    st.caption(
        f"No período 2011 a 2019, o balanço oficial registra "
        f"{formatar_numero(total_oficial)} denúncias em Santa Catarina, contra "
        f"{formatar_numero(total_nosso)} registros de violação neste projeto: "
        f"{formatar_taxa(total_nosso / total_oficial) if total_oficial else ''} registros por "
        "denúncia. É a razão pela qual o painel nunca chama registro de denúncia."
    )


def _render_cobertura(auditoria: Dict[str, Any]) -> None:
    cobertura = auditoria.get("cobertura_por_semestre") or []
    if not cobertura:
        return
    df = pd.DataFrame(cobertura)

    st.markdown("### Cobertura dos indicadores por semestre")
    st.caption(
        "Mostra onde cada indicador existe na série. Um indicador que cai a zero em um "
        "período não significa ausência do fenômeno, e sim ausência do campo que o "
        "identifica naquele arquivo."
    )

    rotulos = {
        "is_crianca": "Crianças e adolescentes",
        "is_mulher": "Mulheres",
        "is_idoso": "Pessoas idosas",
        "is_pcd": "Pessoas com deficiência",
        "is_lgbtqia": "LGBTQIA+",
        "is_prisional_rua": "Prisional e rua",
    }
    tabela = pd.DataFrame({
        "Ano": df["ano"],
        "Sem.": df["semestre"].map(lambda s: "ano" if s == 0 else str(s)),
        "Registros": df["registros"].map(formatar_numero),
        "Denúncias": df["denuncias_unicas"].map(lambda v: formatar_numero(v) if v else "—"),
        "Reg./denúncia": df["fator_expansao"].map(lambda v: formatar_taxa(v) if v else "—"),
        "% penal": df["pct_penal"].map(formatar_percentual),
        "% sem grupo": df["pct_sem_grupo"].map(formatar_percentual),
        **{rotulos[c]: df[c].map(formatar_numero) for c in rotulos if c in df.columns},
    })
    st.dataframe(tabela, hide_index=True, width="stretch", height=380)

    por_ano = df.groupby("ano", as_index=False).agg(
        registros=("registros", "sum"), denuncias=("denuncias_unicas", "sum")
    )
    por_ano["fator"] = (por_ano["registros"] / por_ano["denuncias"]).where(por_ano["denuncias"] > 0)
    serie = por_ano.dropna(subset=["fator"])
    if len(serie) > 1:
        st.markdown("**Registros de violação por denúncia, ao longo do tempo**")
        st.caption(
            "A curva é o motivo pelo qual contagens de registro não são comparáveis entre "
            "anos: o mesmo volume de denúncias produz cada vez mais registros."
        )
        st.plotly_chart(
            series_temporal(
                serie,
                coluna_x="ano",
                series=[("fator", "Registros por denúncia", CATEGORICA[1])],
                rotulo_valor="Registros por denúncia",
                titulo_x="Ano",
                altura=ALTURA_BAIXA,
            ),
            width="stretch",
            key="fator_expansao",
        )


def _render_inventario(auditoria: Dict[str, Any]) -> None:
    inventario = auditoria.get("inventario_arquivos") or []
    if not inventario:
        return

    with st.expander(f"Inventário dos {len(inventario)} arquivos de microdados"):
        st.caption(
            "Para cada arquivo publicado pelo MDHC: era de esquema, volume, denúncias "
            "distintas e quais campos o resolvedor de colunas encontrou. Os campos "
            "ausentes explicam as lacunas dos indicadores."
        )
        df = pd.DataFrame(inventario)
        colunas = {
            "arquivo": "Arquivo",
            "era_esquema": "Era de esquema",
            "linhas_totais_arquivo": "Linhas (Brasil)",
            "linhas_sc": "Linhas (SC)",
            "linhas_sc_distintas": "Linhas distintas (SC)",
            "denuncias_sc_distintas": "Denúncias (SC)",
            "fator_expansao_linhas_por_denuncia": "Reg./denúncia",
            "colunas_no_arquivo": "Colunas",
        }
        presentes = {k: v for k, v in colunas.items() if k in df.columns}
        tabela = df[list(presentes.keys())].rename(columns=presentes)
        for coluna in ("Linhas (Brasil)", "Linhas (SC)", "Linhas distintas (SC)", "Denúncias (SC)"):
            if coluna in tabela.columns:
                tabela[coluna] = tabela[coluna].map(lambda v: formatar_numero(v) if pd.notna(v) else "—")
        st.dataframe(tabela, hide_index=True, width="stretch", height=380)

        ausentes = df[df["campos_ausentes"].map(lambda v: bool(v))] if "campos_ausentes" in df.columns else pd.DataFrame()
        if not ausentes.empty:
            st.caption("Campos ausentes por arquivo:")
            st.dataframe(
                pd.DataFrame({
                    "Arquivo": ausentes["arquivo"],
                    "Campos ausentes": ausentes["campos_ausentes"].map(lambda v: ", ".join(v)),
                }),
                hide_index=True,
                width="stretch",
            )


def _render_hashes(auditoria: Dict[str, Any]) -> None:
    hashes: Dict[str, str] = auditoria.get("arquivos_hashes_sha256") or {}
    if not hashes:
        return
    with st.expander(f"Integridade: SHA-256 dos {len(hashes)} arquivos processados"):
        st.caption(
            "Confira localmente com `shasum -a 256 data/processed/<arquivo>`. "
            f"Processamento em {auditoria.get('timestamp_auditoria')}."
        )
        st.dataframe(
            pd.DataFrame({"Arquivo": list(hashes.keys()), "SHA-256": list(hashes.values())}),
            hide_index=True,
            width="stretch",
        )


def _render_triagem() -> None:
    st.markdown("### Triagem entre indício penal e demanda socioassistencial")
    st.caption(
        "A triagem é automatizada: uma taxonomia de palavras-chave varre o texto da "
        "violação relatada e, quando reconhece um tipo penal, marca a ocorrência como "
        "indício e registra a fundamentação e o órgão de encaminhamento sugerido. "
        "Indica onde há indício a apurar; não é decisão jurídica, não foi validada contra "
        "inquérito ou laudo, e sua precisão não foi medida."
    )

    c1, c2 = st.columns(2)
    with c1:
        with st.expander("Indício de infração penal", expanded=False):
            st.markdown(AJUDA_PENAL)
            st.markdown(
                "**Fundamentação**\n"
                "- Código Penal, Decreto-Lei 2.848/1940: arts. 121, 129, 136, 147, 147-A, "
                "147-B, 213, 217-A\n"
                "- ECA, Lei 8.069/1990: arts. 232 a 244-B\n"
                "- Lei Henry Borel, Lei 14.344/2022\n"
                "- Estatuto da Pessoa Idosa, Lei 10.741/2003: arts. 96 a 108\n"
                "- Lei Maria da Penha, Lei 11.340/2006\n"
                "- Lei de Tortura, Lei 9.455/1997\n"
                "- Lei 7.716/1989 e ADO 26 do STF, racismo e injúria racial"
            )
    with c2:
        with st.expander("Demanda socioassistencial", expanded=False):
            st.markdown(AJUDA_SOCIAL)
            st.markdown(
                "**Fundamentação**\n"
                "- LOAS, Lei 8.742/1993\n"
                "- Tipificação Nacional de Serviços Socioassistenciais, "
                "Resolução CNAS 109/2009\n"
                "- Sistema Único de Assistência Social"
            )

    with st.expander("Como as taxas são calculadas"):
        st.markdown(f"- {AJUDA_TAXA}")
        st.markdown(f"- {AJUDA_DISTANCIA}")


def _render_fontes() -> None:
    st.markdown("### Fontes oficiais")
    st.dataframe(
        pd.DataFrame({
            "Órgão": [f["orgao"] for f in FONTES_OFICIAIS],
            "Conteúdo": [f["descricao"] for f in FONTES_OFICIAIS],
            "Endereço": [f["link"] for f in FONTES_OFICIAIS],
        }),
        hide_index=True,
        width="stretch",
        column_config={"Endereço": st.column_config.LinkColumn("Endereço", display_text="abrir")},
    )
