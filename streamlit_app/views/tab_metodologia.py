"""
Aba 5: Metodologia Jurídica, Fontes Oficiais Gov.br e Auditoria Criptográfica SHA-256.
"""

from pathlib import Path
from typing import Dict, Any
import streamlit as st
from streamlit_app.config import FONTES_OFICIAIS


def render_tab_metodologia(audit_data: Dict[str, Any], root_dir: Path) -> None:
    """Renderiza os fundamentos legais, fontes governamentais e a auditoria de hashes."""
    st.subheader("Metodologia Jurídica e Rastreabilidade Governamental")

    st.markdown("""
    ### Distinção entre "Indício Penal" e "Demanda Socioassistencial"
    O Disque 100 (Disque Direitos Humanos) da Ouvidoria Nacional de Direitos Humanos recebe denúncias de natureza mista.
    Para dotar o Governo do Estado de Santa Catarina de capacidade decisória, foi implementada uma **triagem jurídica estrita**,
    separando demandas de persecução policial e perícia técnica daquelas vocacionadas ao acolhimento social.
    """)

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown("""
        #### 1. Indício de Infração Penal (Polícia Civil / Forense)
        - **Fundamentação Legal:**
          - Código Penal Brasileiro (Decreto-Lei nº 2.848/1940): Arts. 121 (Homicídio), 129 (Lesão Corporal), 136 (Maus-tratos), 213 (Estupro), 217-A (Estupro de Vulnerável).
          - Estatuto da Criança e do Adolescente (Lei nº 8.069/1990): Arts. 232 a 244-B (Crimes em espécie e pornografia infantil).
          - Lei Henry Borel (Lei nº 14.344/2022): Violência doméstica contra crianças e adolescentes.
          - Estatuto da Pessoa Idosa (Lei nº 10.741/2003): Arts. 96 a 108 (Discriminação, apropriação indébita e abandono material).
          - Lei Maria da Penha (Lei nº 11.340/2006): Violência de gênero.
        - **Destinação Institucional:** Envio de notícia-crime para as Delegacias da Polícia Civil (PCSC / DPCAMI) e requisição pericial à Polícia Científica de SC (PCI-SC).
        """)
    with col_m2:
        st.markdown("""
        #### 2. Demanda Socioassistencial (Rede SUAS)
        - **Fundamentação Legal:**
          - Lei Orgânica da Assistência Social - LOAS (Lei nº 8.742/1993).
          - Tipificação Nacional de Serviços Socioassistenciais (Resolução CNAS nº 109/2009).
          - Sistema Único de Assistência Social (SUAS).
        - **Caracterização:** Situações de vulnerabilidade socioeconômica, evasão escolar, desabrigamento voluntário, conflitos intrafamiliares leves e ausência de assistência básica não-dolosa.
        - **Destinação Institucional:** Acompanhamento familiar pelos Centros de Referência de Assistência Social (CRAS), Centros de Referência Especializados (CREAS) e Conselhos Tutelares.
        """)

    st.markdown("### Fontes Oficiais da Internet Governamental (Gov.br)")
    tabela_fontes = "| Órgão / Portal | Link Oficial | Descrição |\n| :--- | :--- | :--- |\n"
    for f in FONTES_OFICIAIS:
        tabela_fontes += f"| **{f['orgao']}** | [{f['link']}]({f['link']}) | {f['descricao']} |\n"
    st.markdown(tabela_fontes)

    # Hashes criptográficos dinâmicos a partir do relatório de auditoria
    hashes = audit_data.get("arquivos_hashes_sha256", {})
    hash_fato = hashes.get(
        "sc_fato_denuncias.parquet",
        "cf136739803d1da8022b5cce79d7196e0f789a346de69b315564cd89ffa335fa"
    )
    hash_kpis = hashes.get(
        "sc_kpis_grupos_municipios.parquet",
        "38496a74658e03a21462b2df77d641c84ce54b2b79b2c4942f918dd308157155"
    )
