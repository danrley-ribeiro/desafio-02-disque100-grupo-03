"""
Aba 3: Capacidade Pericial Forense e Tempo de Resposta da Polícia Científica (PCI-SC).
"""

import pandas as pd
import streamlit as st
from streamlit_app.utils.formatters import format_brazilian


def render_tab_pci(
    df_filtrado: pd.DataFrame,
    df_pci: pd.DataFrame,
    col_penal: str,
    label_escala: str,
    label_periodo: str,
    fator_pop: int
) -> None:
    """Renderiza a análise de distância pericial, vazios críticos e catálogo da PCI-SC."""
    st.subheader("Diagnóstico de Vulnerabilidade e Tempo de Resposta Forense")
    st.markdown("""
    Em infrações penais contra a dignidade sexual e agressões com lesão corporal, a preservação da prova material 
    depende do **tempo de deslocamento até a unidade da Polícia Científica (PCI-SC)** para exame de corpo de delito 
    e coleta do kit de DNA (janela crítica de até 72 horas).
    """)

    # Cálculos dinâmicos da malha de acesso à perícia forense
    muns_imediata = len(df_filtrado[df_filtrado["distancia_pci_km"] < 25.0])
    muns_atencao = len(df_filtrado[(df_filtrado["distancia_pci_km"] >= 25.0) & (df_filtrado["distancia_pci_km"] <= 50.0)])
    muns_vazio = len(df_filtrado[df_filtrado["distancia_pci_km"] > 50.0])

    col_z1, col_z2, col_z3 = st.columns(3)
    with col_z1:
        st.success(f"Zona de Resposta Imediata (< 25 km)\n\n**{muns_imediata} municípios** atendidos em menos de 30 minutos pelas superintendências ou núcleos regionais.")
    with col_z2:
        st.warning(f"Zona de Atenção Moderada (25 a 50 km)\n\n**{muns_atencao} municípios** com tempo estimado de 30 min a 1h por rodovias estaduais e vicinais.")
    with col_z3:
        st.error(f"Vazio Pericial Crítico (> 50 km)\n\n**{muns_vazio} municípios** com deslocamento superior a 1h15, sob risco de perda irrecuperável de vestígios de DNA.")

    st.markdown(f"### Municípios com Maior Pico Criminal Localizados em Distâncias Críticas (> 35 km da PCI) - {label_periodo}")
    df_vazio_calc = df_filtrado[df_filtrado["distancia_pci_km"] >= 35.0].sort_values(by="taxa_exibicao", ascending=False).head(6)

    if not df_vazio_calc.empty:
        df_vazio_tabela = df_vazio_calc[["municipio", "regiao_intermediaria", "populacao_censo_2022", col_penal, "taxa_exibicao", "distancia_pci_km", "pci_proxima"]].copy()
        df_vazio_tabela["distancia_pci_km"] = df_vazio_tabela["distancia_pci_km"].apply(lambda d: f"{d:.1f} km")
        df_vazio_tabela["taxa_exibicao"] = df_vazio_tabela["taxa_exibicao"].apply(lambda t: f"{t:.1f}")
        df_vazio_tabela["populacao_censo_2022"] = df_vazio_tabela["populacao_censo_2022"].apply(lambda p: format_brazilian(p))
        df_vazio_tabela[col_penal] = df_vazio_tabela[col_penal].apply(lambda c: format_brazilian(c))

        st.dataframe(
            df_vazio_tabela.rename(
                columns={
                    "municipio": "Município",
                    "regiao_intermediaria": "Região Intermediária",
                    "populacao_censo_2022": "População",
                    col_penal: "Casos Penais",
                    "taxa_exibicao": f"Taxa ({label_escala})",
                    "distancia_pci_km": "Distância da PCI",
                    "pci_proxima": "Unidade Forense de Referência"
                }
            ),
            hide_index=True,
            width="stretch"
        )

        # Síntese Tática Automatizada
        top1_vazio = df_vazio_calc.iloc[0]
        top_nomes_vazio = ", ".join(df_vazio_calc["municipio"].head(3).tolist())

        solucao_dinamica = (
            f"🛡️ **Solução Tática Proposta Automatizada ({label_periodo}):**\n\n"
            f"No recorte territorial selecionado, o ponto de maior vulnerabilidade forense é **{top1_vazio['municipio']}** "
            f"({top1_vazio['distancia_pci_km']:.1f} km até a {top1_vazio['pci_proxima']}), com taxa criminal de "
            f"**{top1_vazio['taxa_exibicao']:.1f} ocorrências por {fator_pop//1000}k hab**.\n\n"
            f"**Ação Recomendada:** Estruturar **Postos Avançados de Coleta Forense (PACF)** em unidades hospitalares e UPAs "
            f"de referência próximas a **{top_nomes_vazio}**, integrando a Secretaria de Estado da Saúde (SES-SC) à Polícia Científica (PCI-SC). "
            f"Isso assegura a coleta de vestígios biológicos (kit de DNA em crimes sexuais e lesões graves) "
            f"dentro da janela clínica indispensável de até 72 horas, evitando o perecimento da prova pericial."
        )
        st.info(solucao_dinamica)
    else:
        st.success("Não foram identificados municípios em vazio pericial crítico com os filtros territoriais selecionados.")

    with st.expander("Catálogo das 30 Unidades da Polícia Científica de SC"):
        if not df_pci.empty:
            st.dataframe(
                df_pci[["sigla", "nome", "municipio", "tipo", "jurisdicao"]].rename(
                    columns={
                        "sigla": "Sigla",
                        "nome": "Unidade Forense",
                        "municipio": "Município Sede",
                        "tipo": "Tipo de Unidade",
                        "jurisdicao": "Comarcas Atendidas"
                    }
                ),
                hide_index=True,
                width="stretch"
            )

