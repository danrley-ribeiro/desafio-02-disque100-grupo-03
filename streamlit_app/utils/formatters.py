"""
=============================================================================
Formatacao numerica brasileira e derivacao de metricas
=============================================================================
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from streamlit_app.config import (
    FAIXA_DISTANTE,
    FAIXA_INTERMEDIARIA,
    FAIXA_INTERMEDIARIA_KM,
    FAIXA_PROXIMA,
    FAIXA_PROXIMA_KM,
)

# Exibido quando o dado nao existe. Nunca substituimos ausencia por zero nem
# por um valor plausivel: a versao anterior atribuia 30 km de distancia
# pericial a qualquer municipio que faltasse na matriz.
SEM_DADO = "não informado"


def formatar_numero(valor: Optional[float], decimais: int = 0) -> str:
    """
    Formata no padrao brasileiro: 1.234.567 ou 1.234,56.

    Aplica-se apenas ao numero. A versao anterior rodava `.replace(",", ".")`
    sobre paragrafos inteiros, trocando toda virgula gramatical por ponto.

    >>> formatar_numero(1234567)
    '1.234.567'
    >>> formatar_numero(1234.56, 2)
    '1.234,56'
    >>> formatar_numero(-42)
    '-42'
    >>> formatar_numero(None)
    'não informado'
    """
    if valor is None or pd.isna(valor):
        return SEM_DADO
    if decimais == 0:
        return f"{int(round(valor)):,}".replace(",", "\x00").replace("\x00", ".")
    texto = f"{valor:,.{decimais}f}"
    inteiro, _, decimal = texto.rpartition(".")
    return f"{inteiro.replace(',', '.')},{decimal}"


def formatar_taxa(valor: Optional[float], decimais: int = 1) -> str:
    """Taxa por habitante, sempre com uma casa decimal."""
    return formatar_numero(valor, decimais)


def formatar_percentual(valor: Optional[float], decimais: int = 1) -> str:
    if valor is None or pd.isna(valor):
        return SEM_DADO
    return f"{formatar_numero(valor, decimais)}%"


def formatar_km(valor: Optional[float]) -> str:
    if valor is None or pd.isna(valor):
        return SEM_DADO
    return f"{formatar_numero(valor, 1)} km"


def classificar_faixa_distancia(dist_km: Optional[float]) -> str:
    """Faixa de distancia em linha reta ate a unidade pericial."""
    if dist_km is None or pd.isna(dist_km):
        return SEM_DADO
    if dist_km < FAIXA_PROXIMA_KM:
        return FAIXA_PROXIMA
    if dist_km <= FAIXA_INTERMEDIARIA_KM:
        return FAIXA_INTERMEDIARIA
    return FAIXA_DISTANTE


def preparar_metricas(
    df: pd.DataFrame,
    *,
    coluna_total: str,
    coluna_penal: str,
    fator_pop: int,
    semestres: int,
    natureza: str,
) -> pd.DataFrame:
    """
    Deriva as metricas de exibicao do recorte ativo.

    A taxa e anualizada: divide-se pelo numero de semestres efetivamente
    cobertos, e nao por uma constante. A versao anterior dividia sempre por 16,
    mesmo quando o recorte era de um ano so e mesmo com 2026 contribuindo
    apenas um semestre.

    Municipios sem populacao no Censo ficam com taxa indefinida, nao zero.
    """
    out = df.copy()

    out["valor_total"] = out[coluna_total].fillna(0)
    out["valor_penal"] = out[coluna_penal].fillna(0)
    out["valor_social"] = out["valor_total"] - out["valor_penal"]

    pop = out["populacao_censo_2022"]
    pop_valida = pop.where(pop > 0)
    anos = max(semestres, 1) / 2.0

    for origem, destino in (
        ("valor_total", "taxa_total"),
        ("valor_penal", "taxa_penal"),
        ("valor_social", "taxa_social"),
    ):
        out[destino] = (out[origem] / pop_valida / anos) * fator_pop

    total_seguro = out["valor_total"].where(out["valor_total"] > 0)
    out["pct_penal"] = (out["valor_penal"] / total_seguro) * 100.0

    if natureza == "penal":
        out["valor_exibicao"] = out["valor_penal"]
        out["taxa_exibicao"] = out["taxa_penal"]
    elif natureza == "social":
        out["valor_exibicao"] = out["valor_social"]
        out["taxa_exibicao"] = out["taxa_social"]
    else:
        out["valor_exibicao"] = out["valor_total"]
        out["taxa_exibicao"] = out["taxa_total"]

    return out
