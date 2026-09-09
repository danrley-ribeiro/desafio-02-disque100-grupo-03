"""
Aba 2: Análise Estratégica Comparativa por Grupos Vulneráveis.
"""

from typing import List
import pandas as pd
import streamlit as st


def render_tab_grupos(
    df_filtrado: pd.DataFrame,
    pop_total: int,
    fator_pop: int,
    label_escala: str,
    label_periodo: str,
    regioes_escolhidas: List[str]
) -> None:
    """Renderiza a análise comparativa entre os 6 grupos prioritários catalogados."""
    st.subheader("Distribuição Comparativa dos Grupos Vulneráveis em Santa Catarina")
    st.markdown("""
    Esta seção compara o perfil de incidência entre os 6 grupos prioritários catalogados,
    demonstrando a disparidade de gravidade penal entre as tipologias de atendimento.
    """)

    # Agregação geral dos grupos no filtro territorial ativo
    grupos_dados = [
        {
            "Grupo Vulnerável": "Crianças e Adolescentes (ECA)",
            "Total Ocorrências": int(df_filtrado["criancas_total"].sum()),
            "Indício Penal": int(df_filtrado["criancas_penal"].sum()),
            "Demanda Social": int(df_filtrado["criancas_total"].sum() - df_filtrado["criancas_penal"].sum()),
            "Percentual Penal (%)": round((df_filtrado["criancas_penal"].sum() / max(df_filtrado["criancas_total"].sum(), 1)) * 100, 1),
            f"{label_escala}": round((df_filtrado["criancas_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
        },
        {
            "Grupo Vulnerável": "Pessoas Idosas",
            "Total Ocorrências": int(df_filtrado["idosos_total"].sum()),
            "Indício Penal": int(df_filtrado["idosos_penal"].sum()),
            "Demanda Social": int(df_filtrado["idosos_total"].sum() - df_filtrado["idosos_penal"].sum()),
            "Percentual Penal (%)": round((df_filtrado["idosos_penal"].sum() / max(df_filtrado["idosos_total"].sum(), 1)) * 100, 1),
            f"{label_escala}": round((df_filtrado["idosos_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
        },
        {
            "Grupo Vulnerável": "Pessoas com Deficiência (PCD)",
            "Total Ocorrências": int(df_filtrado["pcd_total"].sum()),
            "Indício Penal": int(df_filtrado["pcd_penal"].sum()),
            "Demanda Social": int(df_filtrado["pcd_total"].sum() - df_filtrado["pcd_penal"].sum()),
            "Percentual Penal (%)": round((df_filtrado["pcd_penal"].sum() / max(df_filtrado["pcd_total"].sum(), 1)) * 100, 1),
            f"{label_escala}": round((df_filtrado["pcd_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
        },
        {
            "Grupo Vulnerável": "Mulheres (Violência Doméstica / Gênero)",
            "Total Ocorrências": int(df_filtrado["mulheres_total"].sum()),
            "Indício Penal": int(df_filtrado["mulheres_penal"].sum()),
            "Demanda Social": int(df_filtrado["mulheres_total"].sum() - df_filtrado["mulheres_penal"].sum()),
            "Percentual Penal (%)": round((df_filtrado["mulheres_penal"].sum() / max(df_filtrado["mulheres_total"].sum(), 1)) * 100, 1),
            f"{label_escala}": round((df_filtrado["mulheres_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
        },
        {
            "Grupo Vulnerável": "Sistema Prisional e Situação de Rua",
            "Total Ocorrências": int(df_filtrado["prisional_total"].sum()),
            "Indício Penal": int(df_filtrado["prisional_penal"].sum()),
            "Demanda Social": int(df_filtrado["prisional_total"].sum() - df_filtrado["prisional_penal"].sum()),
            "Percentual Penal (%)": round((df_filtrado["prisional_penal"].sum() / max(df_filtrado["prisional_total"].sum(), 1)) * 100, 1),
            f"{label_escala}": round((df_filtrado["prisional_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
        },
        {
            "Grupo Vulnerável": "População LGBTQIA+",
            "Total Ocorrências": int(df_filtrado["lgbt_total"].sum()),
            "Indício Penal": int(df_filtrado["lgbt_penal"].sum()),
            "Demanda Social": int(df_filtrado["lgbt_total"].sum() - df_filtrado["lgbt_penal"].sum()),
            "Percentual Penal (%)": round((df_filtrado["lgbt_penal"].sum() / max(df_filtrado["lgbt_total"].sum(), 1)) * 100, 1),
            f"{label_escala}": round((df_filtrado["lgbt_total"].sum() / max(pop_total, 1)) * fator_pop, 1)
        }
    ]
    df_grupos_comp = pd.DataFrame(grupos_dados)

    col_g1, col_g2 = st.columns([5, 5])
    with col_g1:
        st.markdown("#### Volume Total por Grupo Vulnerável")
        st.bar_chart(
            data=df_grupos_comp.set_index("Grupo Vulnerável")["Total Ocorrências"],
            color="#2563eb"
        )
    with col_g2:
        st.markdown("#### Taxa de Severidade Penal (% de Casos Criminais)")
        st.bar_chart(
            data=df_grupos_comp.set_index("Grupo Vulnerável")["Percentual Penal (%)"],
            color="#dc2626"
        )

    st.markdown("#### Matriz Sintética de Atendimento por Grupo Vulnerável")
    st.dataframe(df_grupos_comp, hide_index=True, width="stretch")

    # Conclusão Operacional 100% Automatizada e Dinâmica
    df_ord_penal = df_grupos_comp.sort_values(by="Percentual Penal (%)", ascending=False)
    top1_penal = df_ord_penal.iloc[0]
    top2_penal = df_ord_penal.iloc[1]

    df_ord_vol = df_grupos_comp.sort_values(by="Total Ocorrências", ascending=False)
    top1_vol = df_ord_vol.iloc[0]
    top2_vol = df_ord_vol.iloc[1]
    top_social = df_grupos_comp.sort_values(by="Percentual Penal (%)", ascending=True).iloc[0]

    territorio_desc = (
        regioes_escolhidas[0] if (regioes_escolhidas and len(regioes_escolhidas) == 1)
        else ("Regiões Selecionadas" if regioes_escolhidas else "Santa Catarina (Estado Inteiro)")
    )

    conclusao_grupos = (
        f"💡 **Conclusão Operacional Automatizada ({label_periodo} | {territorio_desc}):**\n\n"
        f"• **Severidade Penal Relativa:** O grupo de **{top1_penal['Grupo Vulnerável']}** lidera a gravidade criminal no recorte ativo, "
        f"com **{top1_penal['Percentual Penal (%)']:.1f}%** das denúncias tipificadas como infrações penais (violência física, sexual ou ameaça), "
        f"seguido por **{top2_penal['Grupo Vulnerável']}** (**{top2_penal['Percentual Penal (%)']:.1f}%**), "
        f"demandando atuação prioritária de inquéritos policiais da PCSC e perícias da PCI-SC.\n\n"
        f"• **Volume Absoluto e Pressão Socioassistencial:** A maior sobrecarga operacional quantitativa recai sobre "
        f"**{top1_vol['Grupo Vulnerável']}** ({int(top1_vol['Total Ocorrências']):,} ocorrências) e "
        f"**{top2_vol['Grupo Vulnerável']}** ({int(top2_vol['Total Ocorrências']):,} ocorrências). "
        f"O grupo de **{top_social['Grupo Vulnerável']}** registra o maior contingente relativo de demandas socioassistenciais "
        f"({100.0 - top_social['Percentual Penal (%)']:.1f}%), vocacionado aos atendimentos dos Centros de Referência de Assistência Social (CRAS/CREAS)."
    ).replace(",", ".")

    st.info(conclusao_grupos)

