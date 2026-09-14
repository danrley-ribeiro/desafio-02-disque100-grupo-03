#!/usr/bin/env python3
"""
=============================================================================
Eixos rodoviarios de referencia de Santa Catarina
=============================================================================
Tracados de referencia das principais rodovias federais e estaduais do estado,
usados como camada de contexto nos mapas.

NATUREZA DO DADO, que os mapas precisam declarar: estes tracados sao
ESQUEMATICOS. Cada eixo e uma polilinha de poucos vertices que segue o corredor
aproximado da rodovia, e nao a geometria oficial do DNIT ou do DEINFRA. Servem
para situar o leitor sobre por onde corre a ligacao entre regioes; nao servem
para medir distancia, extensao nem tempo de percurso.

A definicao vive aqui, e nao dentro do gerador do mapa Folium, para que o
painel e o mapa pre-gerado usem exatamente os mesmos eixos.
=============================================================================
"""

from __future__ import annotations

from typing import Any, Dict, List

__all__ = ["EIXOS_RODOVIARIOS", "AVISO_TRACADO", "eixos_como_geojson"]

AVISO_TRACADO = (
    "Traçado esquemático dos corredores rodoviários, com poucos vértices por eixo. "
    "Não é a geometria oficial do DNIT ou do DEINFRA e não serve para medir extensão "
    "ou tempo de percurso."
)

# tipo: "federal" ou "estadual". A largura da linha no mapa vem do tipo, nao de
# uma cor por rodovia: quatorze matizes diferentes competiam com a escala de cor
# dos dados no mapa anterior.
EIXOS_RODOVIARIOS: List[Dict[str, Any]] = [
    # Federais
    {"nome": "BR-101", "descricao": "Eixo litorâneo norte-sul", "tipo": "federal",
     "coords": [[-26.00, -48.62], [-26.25, -48.82], [-26.90, -48.66], [-27.12, -48.60],
                [-27.59, -48.62], [-27.65, -48.67], [-28.28, -48.70], [-28.47, -49.00],
                [-28.67, -49.30], [-28.94, -49.49], [-29.32, -49.72]]},
    {"nome": "BR-282", "descricao": "Eixo transversal leste-oeste", "tipo": "federal",
     "coords": [[-27.60, -48.58], [-27.65, -48.67], [-27.70, -49.10], [-27.75, -49.50],
                [-27.81, -50.32], [-27.40, -51.22], [-27.17, -51.50], [-26.87, -52.40],
                [-27.10, -52.61], [-26.72, -53.51]]},
    {"nome": "BR-470", "descricao": "Vale do Itajaí e portos", "tipo": "federal",
     "coords": [[-26.88, -48.65], [-26.90, -48.80], [-26.91, -49.06], [-27.05, -49.30],
                [-27.21, -49.64], [-27.12, -50.15], [-27.28, -50.58], [-27.40, -51.22]]},
    {"nome": "BR-116", "descricao": "Planalto norte-sul", "tipo": "federal",
     "coords": [[-26.11, -49.80], [-26.50, -50.10], [-26.90, -50.25], [-27.81, -50.32],
                [-28.30, -50.60]]},
    {"nome": "BR-280", "descricao": "Norte e porto de São Francisco do Sul", "tipo": "federal",
     "coords": [[-26.24, -48.63], [-26.30, -48.84], [-26.48, -49.07], [-26.35, -49.40],
                [-26.11, -49.80], [-26.17, -50.39], [-26.23, -51.07]]},
    {"nome": "BR-153", "descricao": "Transbrasiliana", "tipo": "federal",
     "coords": [[-26.10, -51.05], [-26.70, -51.50], [-27.23, -52.02], [-27.40, -52.10]]},
    {"nome": "BR-163", "descricao": "Extremo oeste", "tipo": "federal",
     "coords": [[-26.25, -53.60], [-26.72, -53.51], [-27.10, -53.60]]},

    # Estaduais
    {"nome": "SC-401", "descricao": "Norte da Ilha, Florianópolis", "tipo": "estadual",
     "coords": [[-27.58, -48.54], [-27.50, -48.50], [-27.43, -48.45]]},
    {"nome": "SC-405", "descricao": "Sul da Ilha e aeroporto, Florianópolis", "tipo": "estadual",
     "coords": [[-27.60, -48.53], [-27.68, -48.51], [-27.75, -48.50]]},
    {"nome": "SC-108", "descricao": "Joinville, Blumenau, Brusque e Criciúma", "tipo": "estadual",
     "coords": [[-26.30, -48.84], [-26.48, -49.00], [-26.91, -49.06], [-27.09, -48.91],
                [-28.10, -49.20], [-28.67, -49.37]]},
    {"nome": "SC-486", "descricao": "Itajaí e Brusque", "tipo": "estadual",
     "coords": [[-26.90, -48.66], [-27.00, -48.78], [-27.09, -48.91]]},
    {"nome": "SC-350", "descricao": "Rio do Sul, Ituporanga e Caçador", "tipo": "estadual",
     "coords": [[-27.21, -49.64], [-27.41, -49.60], [-26.77, -51.01]]},
    {"nome": "SC-355", "descricao": "Videira, Fraiburgo e Lebon Régis", "tipo": "estadual",
     "coords": [[-27.00, -51.15], [-27.02, -50.92], [-26.92, -50.69]]},
    {"nome": "SC-114", "descricao": "Lages, São Joaquim e Taió", "tipo": "estadual",
     "coords": [[-27.11, -49.99], [-27.81, -50.32], [-28.29, -49.93]]},
    {"nome": "SC-390", "descricao": "Serra do Rio do Rastro, São Joaquim e Tubarão", "tipo": "estadual",
     "coords": [[-28.29, -49.93], [-28.39, -49.56], [-28.47, -49.00]]},
    {"nome": "SC-445", "descricao": "Criciúma e Balneário Rincão", "tipo": "estadual",
     "coords": [[-28.67, -49.37], [-28.75, -49.28], [-28.83, -49.23]]},
    {"nome": "SC-283", "descricao": "Chapecó, Seara e Concórdia", "tipo": "estadual",
     "coords": [[-27.10, -52.61], [-27.15, -52.31], [-27.23, -52.02]]},
    {"nome": "SC-157", "descricao": "Chapecó, Coronel Freitas e São Lourenço do Oeste", "tipo": "estadual",
     "coords": [[-27.10, -52.61], [-26.90, -52.70], [-26.35, -52.85]]},
    {"nome": "SC-480", "descricao": "Chapecó e Goio-Ên", "tipo": "estadual",
     "coords": [[-27.10, -52.61], [-27.25, -52.60], [-27.35, -52.65]]},
    {"nome": "SC-418", "descricao": "Serra Dona Francisca, Joinville e São Bento do Sul", "tipo": "estadual",
     "coords": [[-26.30, -48.84], [-26.23, -49.05], [-26.25, -49.37]]},
]

# Cores usadas apenas pelo mapa Folium pre-gerado, que desenha um eixo por cor.
_CORES_LEGADAS = {"federal": "#ef4444", "estadual": "#0ea5e9"}


def eixos_como_geojson() -> List[Dict[str, Any]]:
    """
    Formato consumido pelo gerador do mapa Folium, que espera `color` e `weight`.

    Mantem a assinatura antiga para nao alterar o gerador, acrescentando o
    rotulo descritivo ao nome.
    """
    saida = []
    for e in EIXOS_RODOVIARIOS:
        saida.append({
            "nome": f"{e['nome']} ({e['descricao']})",
            "tipo": e["tipo"],
            "coords": e["coords"],
            "color": _CORES_LEGADAS[e["tipo"]],
            "weight": 3.8 if e["tipo"] == "federal" else 3.0,
        })
    return saida
