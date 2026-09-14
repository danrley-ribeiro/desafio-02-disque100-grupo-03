#!/usr/bin/env python3
"""
=============================================================================
Malha municipal de SC e matriz de distancia ate a Policia Cientifica
=============================================================================
Produz os dois artefatos geoespaciais que o painel consome:

  data/processed/sc_malha_municipios.geojson
      Malha dos 295 municipios de Santa Catarina, da API de Malhas do IBGE
      (v4, qualidade minima), com a orientacao de vertices corrigida para
      D3/Plotly. Fica versionada para que o painel funcione sem rede.

  data/processed/sc_municipios_distancia_pci.json
      Para cada municipio: centroide geometrico, unidade da Policia Cientifica
      mais proxima, distancia e faixa de distancia.

Por que este script existe: a matriz de distancia era publicada sem nenhum
script gerador no repositorio, de modo que nao havia como reproduzi-la nem
saber como havia sido calculada.

Metodo e sua limitacao, que o painel precisa declarar: a distancia e geodesica
(haversine), medida em linha reta entre o centroide do municipio e a unidade
pericial. Nao e distancia rodoviaria e nao sustenta, por si, estimativa de
tempo de deslocamento. Em relevo de serra a distancia por estrada chega a ser
uma vez e meia a distancia em linha reta.

Uso:
    python3 scripts/gerar_geo_pci_sc.py
=============================================================================
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "scripts" else CURRENT_DIR
for _p in (str(CURRENT_DIR), str(ROOT_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from eixos_rodoviarios_sc import AVISO_TRACADO, EIXOS_RODOVIARIOS
from generate_sc_disque100_folium_dashboard import (
    IBGEClient,
    get_feature_centroid,
    haversine_km,
)

# Faixas de distancia em linha reta. Sao faixas de distancia, nao isocronas:
# o nome de cada faixa nao afirma tempo de deslocamento.
FAIXA_PROXIMA_KM = 25.0
FAIXA_INTERMEDIARIA_KM = 50.0

FAIXA_PROXIMA = "Até 25 km da unidade pericial"
FAIXA_INTERMEDIARIA = "De 25 a 50 km da unidade pericial"
FAIXA_DISTANTE = "Acima de 50 km da unidade pericial"


def classificar_faixa(dist_km: float) -> str:
    if dist_km < FAIXA_PROXIMA_KM:
        return FAIXA_PROXIMA
    if dist_km <= FAIXA_INTERMEDIARIA_KM:
        return FAIXA_INTERMEDIARIA
    return FAIXA_DISTANTE


def carregar_json(caminho: Path) -> Any:
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def gerar(root_dir: Path) -> None:
    proc = root_dir / "data" / "processed"
    proc.mkdir(parents=True, exist_ok=True)

    client = IBGEClient()

    # 1. Malha municipal, com a correcao de orientacao de vertices aplicada
    #    pelo proprio cliente (regra da mao direita, exigida por D3/Plotly).
    print("Obtendo malha municipal de SC na API de Malhas do IBGE...")
    malha = client.get_malha_municipios_uf_geojson(
        uf="SC", intrarregiao="municipio", qualidade="minima"
    )
    features = malha.get("features", [])
    destino_malha = proc / "sc_malha_municipios.geojson"
    with open(destino_malha, "w", encoding="utf-8") as f:
        json.dump(malha, f, ensure_ascii=False, separators=(",", ":"))
    print(
        f"  {destino_malha.name}: {len(features)} municipios, "
        f"{destino_malha.stat().st_size / 1024:.0f} KB"
    )

    # 2. Metadados municipais e unidades periciais
    df_mun = client.get_municipios_df(uf="SC", engine="polars")
    meta_por_codigo: Dict[str, Dict[str, Any]] = {
        str(r["municipio-id"]): {
            "municipio": r["municipio-nome"],
            "regiao_intermediaria": r["regiao-intermediaria-nome"],
            "regiao_imediata": r["regiao-imediata-nome"],
        }
        for r in df_mun.to_dicts()
    }

    pop = carregar_json(proc / "sc_censo_2022_populacao.json")
    unidades: List[Dict[str, Any]] = carregar_json(proc / "unidades_policia_cientifica_sc.json")
    unidades = [u for u in unidades if u.get("latitude") and u.get("longitude")]
    print(f"Unidades periciais georreferenciadas: {len(unidades)}")

    # 3. Centroide de cada municipio e unidade mais proxima
    matriz: Dict[str, Dict[str, Any]] = {}
    sem_centroide: List[str] = []

    for feat in features:
        cid = str(feat.get("properties", {}).get("codarea", "")).strip()
        if not cid:
            continue
        lat, lng = get_feature_centroid(feat)
        if lat is None or lng is None:
            sem_centroide.append(cid)
            continue

        proxima = min(
            unidades,
            key=lambda u: haversine_km(lat, lng, u["latitude"], u["longitude"]),
        )
        dist = haversine_km(lat, lng, proxima["latitude"], proxima["longitude"])
        meta = meta_por_codigo.get(cid, {})

        matriz[cid] = {
            "ibge_code": cid,
            "municipio": meta.get("municipio"),
            "regiao_intermediaria": meta.get("regiao_intermediaria"),
            "regiao_imediata": meta.get("regiao_imediata"),
            "populacao_censo_2022": pop.get(cid),
            "lat": round(lat, 5),
            "lng": round(lng, 5),
            "distancia_pci_km_linha_reta": round(dist, 1),
            "pci_proxima": proxima.get("nome_unidade"),
            "pci_proxima_municipio": proxima.get("municipio"),
            "faixa_distancia": classificar_faixa(dist),
        }

    if sem_centroide:
        print(f"  Aviso: {len(sem_centroide)} municipios sem centroide calculavel: {sem_centroide}")

    saida = {
        "metadata": {
            "metodo": "haversine_geodesico",
            "descricao": (
                "Distância em linha reta entre o centroide geométrico do município e a "
                "unidade da Polícia Científica mais próxima. Não é distância rodoviária "
                "e não sustenta, por si, estimativa de tempo de deslocamento."
            ),
            "raio_terrestre_km": 6371.0,
            "fonte_malha": "IBGE, API de Malhas v4, qualidade mínima",
            "fonte_unidades": "Polícia Científica de Santa Catarina, portal de unidades",
            "fonte_populacao": "IBGE, Censo Demográfico 2022, tabela SIDRA 4714",
            "faixas_km": {
                FAIXA_PROXIMA: f"< {FAIXA_PROXIMA_KM:.0f}",
                FAIXA_INTERMEDIARIA: f"{FAIXA_PROXIMA_KM:.0f} a {FAIXA_INTERMEDIARIA_KM:.0f}",
                FAIXA_DISTANTE: f"> {FAIXA_INTERMEDIARIA_KM:.0f}",
            },
            "municipios": len(matriz),
            "unidades_periciais": len(unidades),
        },
        "municipios": matriz,
    }

    # 4. Eixos rodoviarios de referencia, para a camada de contexto do mapa
    destino_eixos = proc / "sc_eixos_rodoviarios.json"
    with open(destino_eixos, "w", encoding="utf-8") as f:
        json.dump(
            {
                "metadata": {
                    "natureza": "tracado esquematico",
                    "advertencia": AVISO_TRACADO,
                    "eixos": len(EIXOS_RODOVIARIOS),
                    "federais": sum(1 for e in EIXOS_RODOVIARIOS if e["tipo"] == "federal"),
                    "estaduais": sum(1 for e in EIXOS_RODOVIARIOS if e["tipo"] == "estadual"),
                },
                "eixos": EIXOS_RODOVIARIOS,
            },
            f,
            ensure_ascii=False,
            indent=1,
        )
    print(f"  {destino_eixos.name}: {len(EIXOS_RODOVIARIOS)} eixos rodoviarios de referencia")

    destino_matriz = proc / "sc_municipios_distancia_pci.json"
    with open(destino_matriz, "w", encoding="utf-8") as f:
        json.dump(saida, f, ensure_ascii=False, indent=1)

    distancias = sorted(v["distancia_pci_km_linha_reta"] for v in matriz.values())
    contagem: Dict[str, int] = {}
    for v in matriz.values():
        contagem[v["faixa_distancia"]] = contagem.get(v["faixa_distancia"], 0) + 1

    print(f"  {destino_matriz.name}: {len(matriz)} municipios")
    if distancias:
        mediana = distancias[len(distancias) // 2]
        print(f"  distancia em linha reta: minima {distancias[0]} km, mediana {mediana} km, maxima {distancias[-1]} km")
    for faixa in (FAIXA_PROXIMA, FAIXA_INTERMEDIARIA, FAIXA_DISTANTE):
        print(f"  {faixa}: {contagem.get(faixa, 0)} municipios")

    acima_50 = sorted(
        ((v["distancia_pci_km_linha_reta"], v["municipio"]) for v in matriz.values()
         if v["faixa_distancia"] == FAIXA_DISTANTE),
        reverse=True,
    )
    if acima_50:
        print("  Municipios acima de 50 km: " + ", ".join(f"{n} ({d} km)" for d, n in acima_50))


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    if base.name == "scripts":
        base = base.parent
    gerar(base)
