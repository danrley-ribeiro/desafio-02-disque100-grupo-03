"""
Funções utilitárias de formatação numérica brasileira e enriquecimento analítico.
"""

from typing import Dict, Any, Tuple
import pandas as pd


def format_brazilian(valor: float, casas_decimais: int = 0) -> str:
    """Formata números no padrão brasileiro: 1.234.567 ou 1.234,56."""
    if pd.isna(valor):
        return "0"
    if casas_decimais == 0:
        return f"{int(round(valor)):,}".replace(",", ".")
    formatado = f"{valor:,.{casas_decimais}f}"
    # Inverte vírgulas e pontos
    partes = formatado.split(".")
    inteiro = partes[0].replace(",", ".")
    decimal = partes[1] if len(partes) > 1 else "0"
    return f"{inteiro},{decimal}"


def preparar_df_metricas(
    df_filtrado: pd.DataFrame,
    col_total: str,
    col_penal: str,
    fator_pop: int,
    metric_type_code: str,
    pci_dist_map: Dict[str, Any],
    label_escala: str
) -> Tuple[pd.DataFrame, str]:
    """
    Enriquece o DataFrame com distâncias da PCI, taxas proporcionais ajustadas à escala e métrica ativa.
    """
    df = df_filtrado.copy()

    # Enriquecimento com matriz de distâncias e unidades PCI
    df["distancia_pci_km"] = df["ibge_code"].astype(str).map(
        lambda c: pci_dist_map.get(c, {}).get("distancia_pci_km", 30.0)
    )
    df["pci_proxima"] = df["ibge_code"].astype(str).map(
        lambda c: pci_dist_map.get(c, {}).get("pci_proxima", "PCI Regional")
    )
    df["zona_resposta"] = df["ibge_code"].astype(str).map(
        lambda c: pci_dist_map.get(c, {}).get("zona_resposta", "Atenção (25 a 50 km)")
    )

    pop_safe = df["populacao_censo_2022"].clip(lower=1)
    df["taxa_total_exibicao"] = (df[col_total] / pop_safe) * fator_pop
    df["taxa_penal_exibicao"] = (df[col_penal] / pop_safe) * fator_pop
    df["demanda_social"] = df[col_total] - df[col_penal]
    df["taxa_social_exibicao"] = (df["demanda_social"] / pop_safe) * fator_pop
    
    total_safe = df[col_total].clip(lower=1)
    df["pct_penal_mun"] = (df[col_penal] / total_safe) * 100.0

    # Determinação da métrica ativa para ranking e gráficos
    if metric_type_code == "penal":
        df["taxa_exibicao"] = df["taxa_penal_exibicao"]
        label_metrica_ativa = f"Indício Penal ({label_escala})"
    elif metric_type_code == "social":
        df["taxa_exibicao"] = df["taxa_social_exibicao"]
        label_metrica_ativa = f"Demanda Socioassistencial ({label_escala})"
    else:
        df["taxa_exibicao"] = df["taxa_total_exibicao"]
        label_metrica_ativa = f"Total de Ocorrências ({label_escala})"

    return df, label_metrica_ativa

