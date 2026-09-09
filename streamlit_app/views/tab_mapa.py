"""
Aba 1: Mapa Territorial Interativo e Picos de Incidência Proporcional.
"""

from pathlib import Path
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


def render_tab_mapa(
    df_filtrado: pd.DataFrame,
    label_metrica_ativa: str,
    fator_pop: int,
    folium_topic: str,
    metric_type_code: str,
    region_code: str,
    year_param: str,
    camada_clusters: bool,
    camada_pci: bool,
    camada_rodovias: bool,
    root_dir: Path
) -> None:
    """Renderiza o mapa Folium integrado e o ranking dos 10 maiores picos proporcionais."""
    st.subheader("Visualização Cartográfica e Focos Espaciais")
    st.caption(
        f"Malhas vetoriais oficiais dos 295 municípios, rodovias de ligação, 30 unidades da PCI-SC e os 10 maiores picos proporcionais na base de {fator_pop:,} habitantes ({label_metrica_ativa}).".replace(",", ".")
    )

    map_candidates = [
        root_dir / "dashboards" / "dashboard_sc_disque100_folium.html",
        root_dir / "dashboard_sc_disque100_folium.html"
    ]
    html_map_path = next((p for p in map_candidates if p.exists()), None)

    if html_map_path and html_map_path.exists():
        with open(html_map_path, "r", encoding="utf-8") as f:
            raw_folium_html = f.read()

        # Injeção dinâmica do estado dos filtros do Streamlit diretamente no DOM do Leaflet
        config_injection = f"""
        <script>
            window.ACTIVE_STREAMLIT_CONFIG = {{
                topic: "{folium_topic}",
                metricType: "{metric_type_code}",
                scale: {fator_pop},
                region: "{region_code}",
                year: "{year_param}",
                showClusters: {str(camada_clusters).lower()},
                showPCI: {str(camada_pci).lower()},
                showRoads: {str(camada_rodovias).lower()}
            }};
            (function applyNow() {{
                if (typeof window.applyActiveFilters === 'function') {{
                    window.applyActiveFilters(window.ACTIVE_STREAMLIT_CONFIG);
                }} else {{
                    setTimeout(applyNow, 50);
                }}
            }})();
        </script>
        """

        folium_html = raw_folium_html.replace("<head>", f"<head>\n{config_injection}\n")
        if "</body>" in folium_html:
            folium_html = folium_html.replace("</body>", f"{config_injection}\n</body>")

        if hasattr(st, "iframe"):
            st.iframe(folium_html, height=720, width="stretch")
        else:
            components.html(folium_html, height=720, scrolling=False)
    else:
        st.warning("Arquivo do mapa georreferenciado não encontrado. Execute `python3 scripts/generate_sc_disque100_folium_dashboard.py`.")

    st.markdown(f"### Top 10 Municípios com Maior Concentração Proporcional - {label_metrica_ativa}")
    df_top10 = df_filtrado.sort_values(by="taxa_exibicao", ascending=False).head(10)
    st.bar_chart(
        data=df_top10.set_index("municipio")["taxa_exibicao"],
        color="#3b82f6"
    )

