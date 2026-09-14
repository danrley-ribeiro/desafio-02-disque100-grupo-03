#!/usr/bin/env python3
"""
=============================================================================
Dashboard Integrado de Santa Catarina: Disque 100 + Censo 2022 + PCI + Rodovias
=============================================================================
Dashboard interativo completo com:
  1. Motor Leaflet reativo com filtros dinâmicos de:
     - Nível Territorial: Municípios, Regiões Intermediárias ou Ambos.
     - Métrica: Total a cada 10k hab (Proporção dos Picos), Taxa Anual 10k hab,
       Taxa Anual por 100k hab, Total Histórico ou Média Anual.
     - Tópicos: Todos, Crianças, Idosos, Mulheres, LGBTQIA+, Situação de Rua,
       Pessoas com Deficiência, Restrição de Liberdade, Igualdade Racial, Cidadania.
  2. Camada Especial de Pontos de Pico (Top 10 por Categoria):
     - 10 pontos de pico com máxima concentração proporcional (a cada 10k hab).
     - Marcadores Leaflet com ícones personalizados por categoria e insígnias #1–#10.
     - Efeito radar/pulso e realce espacial de concentração regional (clusters).
     - Tooltips e popups ricos com comparação de dados, rodovias e PCI mais próxima.
     - Navegação interativa "clique para voar" até o ponto de pico no mapa.
  3. Inspeção por Cursor Tooltip (Sticky):
     - Tooltip dinâmico colado ao cursor com setTooltipContent.
  4. Hierarquia visual estrita de Z-Index via Leaflet Panes sem bloqueio de ponteiro:
     - Topo Máximo: Pontos de Pico (peaksPane: 700)
     - Topo Alto: 30 Unidades da Polícia Científica (pciPane: 600)
     - Meio-Alto: Rodovias Federais e Estaduais (roadsPane: 500)
     - Meio: Municípios (municipalitiesPane: 450)
     - Base: Regiões Intermediárias (regionsPane: 400 - Silhueta no modo Ambos)
  5. Metadados de Infraestrutura e Rodovias por Região Intermediária.
  6. Recalibração dinâmica da escala de cores (Choropleth reativo em tempo real).
  7. Métricas claras e formatadas no padrão brasileiro (Censo 2022).
  8. Cards dinâmicos com totais, taxas médias e municípios/regiões líderes.
=============================================================================
"""

import sys
import os
import glob
import re
import json
import math
from pathlib import Path
from typing import Dict, Any, List

import polars as pl
import folium
import requests

# Importa IBGEClient com resolução dinâmica de raiz
CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "scripts" else CURRENT_DIR
sys.path.append(str(ROOT_DIR / ".agents" / "skills" / "ibge-data-analysis" / "scripts"))
try:
    from ibge_client import IBGEClient
except ImportError:
    sys.path.append(str(ROOT_DIR / "scripts"))
    from ibge_client import IBGEClient


TOPICS_MAP = {
    "total": "Todos os Incidentes (Visão Geral)",
    "crianca": "Crianças e Adolescentes (ECA)",
    "mulher": "Mulheres (Violência de Gênero)",
    "idoso": "Pessoas Idosas (Estatuto do Idoso)",
    "pcd": "Pessoas com Deficiência (PCD)",
    "lgbt": "População LGBTQIA+",
    "preso": "Sistema Prisional e Situação de Rua"
}

TOPIC_ICONS = {
    "total": "",
    "crianca": "",
    "mulher": "",
    "idoso": "",
    "pcd": "",
    "lgbt": "",
    "preso": ""
}

REGION_METADATA = {
    "Florianópolis": {
        "pci_superintendencias": ["Florianópolis (PCI/SRFLN)", "Palhoça (PCI/SRPAL)"],
        "pci_nucleos": ["São José (PCI/SRPAL/NRSJS)"],
        "pci_total_unidades": 3,
        "rodovias_principais": ["BR-101", "BR-282", "SC-401", "SC-405", "SC-281"]
    },
    "Joinville": {
        "pci_superintendencias": ["Joinville (PCI/SRJOI)"],
        "pci_nucleos": ["Jaraguá do Sul", "São Bento do Sul", "Canoinhas", "Mafra", "Porto União"],
        "pci_total_unidades": 6,
        "rodovias_principais": ["BR-101", "BR-280", "BR-116", "SC-418", "SC-108", "SC-477"]
    },
    "Blumenau": {
        "pci_superintendencias": ["Blumenau (PCI/SRBLU)", "Balneário Camboriú (PCI/SRBCA)"],
        "pci_nucleos": ["Itajaí", "Brusque", "Rio do Sul"],
        "pci_total_unidades": 5,
        "rodovias_principais": ["BR-101", "BR-470", "SC-108", "SC-486", "SC-350"]
    },
    "Criciúma": {
        "pci_superintendencias": ["Criciúma (PCI/SRCRI)"],
        "pci_nucleos": ["Tubarão", "Araranguá", "Laguna"],
        "pci_total_unidades": 4,
        "rodovias_principais": ["BR-101", "SC-445", "SC-370", "SC-390", "SC-100"]
    },
    "Chapecó": {
        "pci_superintendencias": ["Chapecó (PCI/SRCCO)"],
        "pci_nucleos": ["Concórdia", "Xanxerê", "São Lourenço do Oeste", "São Miguel do Oeste"],
        "pci_total_unidades": 5,
        "rodovias_principais": ["BR-282", "BR-153", "BR-158", "BR-163", "BR-480", "SC-283", "SC-157", "SC-480"]
    },
    "Caçador": {
        "pci_superintendencias": ["Caçador (PCI/SRCDR)"],
        "pci_nucleos": ["Videira", "Joaçaba", "Campos Novos"],
        "pci_total_unidades": 4,
        "rodovias_principais": ["BR-282", "BR-470", "SC-350", "SC-355", "SC-135", "SC-150"]
    },
    "Lages": {
        "pci_superintendencias": ["Lages (PCI/SRLGS)"],
        "pci_nucleos": ["Curitibanos", "São Joaquim"],
        "pci_total_unidades": 3,
        "rodovias_principais": ["BR-282", "BR-116", "BR-470", "SC-114", "SC-390", "SC-120"]
    }
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula a distância em linha reta na superfície terrestre em quilômetros."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def polygon_centroid(coords: List[List[float]]) -> tuple:
    """Calcula o centróide ponderado pela área de um anel de coordenadas [lng, lat]."""
    area = 0.0
    cx = 0.0
    cy = 0.0
    n = len(coords)
    for i in range(n - 1):
        xi, yi = coords[i][0], coords[i][1]
        xj, yj = coords[i + 1][0], coords[i + 1][1]
        cross = (xi * yj - xj * yi)
        area += cross
        cx += (xi + xj) * cross
        cy += (yi + yj) * cross
    area *= 0.5
    if abs(area) < 1e-9:
        avg_x = sum(c[0] for c in coords) / n
        avg_y = sum(c[1] for c in coords) / n
        return avg_x, avg_y, 0.0
    cx /= (6.0 * area)
    cy /= (6.0 * area)
    return cx, cy, abs(area)


def get_feature_centroid(feat: Dict[str, Any]) -> tuple:
    """Retorna (latitude, longitude) do centroide geométrico de uma feature GeoJSON."""
    geom = feat["geometry"]
    gtype = geom["type"]
    coords = geom["coordinates"]
    if gtype == "Polygon":
        cx, cy, _ = polygon_centroid(coords[0])
        return cy, cx  # lat, lng
    elif gtype == "MultiPolygon":
        total_area = 0.0
        sum_lat = 0.0
        sum_lng = 0.0
        for poly in coords:
            cx, cy, a = polygon_centroid(poly[0])
            total_area += a
            sum_lat += cy * a
            sum_lng += cx * a
        if total_area > 0:
            return sum_lat / total_area, sum_lng / total_area
        return cy, cx
    return -27.24, -50.21


def classify_topic(raw_group: str) -> str:
    """Classifica o registro bruto em uma das chaves canônicas."""
    if not raw_group or raw_group == "null":
        return "outros"
    g = str(raw_group).strip().upper()
    
    if "LGBT" in g or "GÊNERO" in g or "SEXUAL" in g or "TRANS" in g or "HOMOFOB" in g:
        return "lgbt"
    elif "RUA" in g or "DESABRIGAD" in g:
        return "rua"
    elif "MULHER" in g or "FEMIN" in g:
        return "mulher"
    elif "CRIAN" in g or "ADOLESC" in g or "INFÂN" in g:
        return "crianca"
    elif "IDOSA" in g or "IDOSO" in g or "TERCEIRA IDADE" in g:
        return "idoso"
    elif "DEFICI" in g or "PCD" in g or "ACF" in g:
        return "pcd"
    elif "LIBERDADE" in g or "PRISION" in g or "CÁRCERE" in g or "PRESO" in g:
        return "preso"
    elif "RACIAL" in g or "NEGRO" in g or "INDÍGEN" in g or "QUILOMB" in g or "CIGANO" in g or "ÉTNIC" in g:
        return "racial"
    else:
        return "outros"


def fetch_sc_population_censo_2022() -> Dict[str, int]:
    """Obtém a população oficial dos 295 municípios de SC via Censo 2022 (IBGE SIDRA ou Cache Local)."""
    cache_candidates = [
        ROOT_DIR / "data" / "processed" / "sc_censo_2022_populacao.json",
        ROOT_DIR / "sc_censo_2022_populacao.json",
        CURRENT_DIR / "sc_censo_2022_populacao.json"
    ]
    cache_file = next((p for p in cache_candidates if p.exists()), cache_candidates[0])
    if cache_file and cache_file.exists():
        try:
            print(f"Carregando população oficial dos 295 municípios de SC do cache local ({cache_file.name})...")
            with open(cache_file, "r", encoding="utf-8") as f:
                pop_map = json.load(f)
                if len(pop_map) >= 290:
                    return pop_map
        except Exception as e:
            print(f"Erro ao ler cache local de população: {e}")

    print("Obtendo população oficial dos 295 municípios de Santa Catarina (Censo 2022 via SIDRA)...")
    url = "https://servicodados.ibge.gov.br/api/v3/agregados/4714/periodos/2022/variaveis/93?localidades=N6[N3[42]]"
    pop_map = {}
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            data = r.json()
            series = data[0]["resultados"][0]["series"]
            for s in series:
                cid = str(s["localidade"]["id"])
                val = int(s["serie"]["2022"])
                pop_map[cid] = val
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(pop_map, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Erro ao consultar SIDRA: {e}")

    fallback_defaults = {
        "4205407": 537213, "4209102": 616323, "4202404": 361261, "4216602": 270295,
        "4208203": 264054, "4204202": 254781, "4204608": 214493, "4211900": 222506,
        "4208906": 182660, "4209300": 164981, "4202909": 141385, "4218707": 110088,
        "4202008": 139155, "4203006": 73720,  "4204806": 40045,  "4209003": 30146,
        "4210100": 55286,  "4213609": 32970,  "4214805": 72587,  "4215802": 86317,
        "4216503": 25939,  "4216909": 22690,  "4217204": 43790,  "4219309": 55625,
        "4219507": 51642,  "4209409": 42785,  "4203600": 36932,  "4203808": 55016,
        "4204301": 81646,  "4201406": 67110,  "4210035": 1778   # Macieira
    }
    for cid, val in fallback_defaults.items():
        if cid not in pop_map or pop_map[cid] <= 0:
            pop_map[cid] = val

    return pop_map


def process_disque100_sc_data(parquet_dir: Path, df_ibge_sc: pl.DataFrame, pop_map: Dict[str, int]) -> Dict[str, Any]:
    """Processa todos os 22 arquivos Parquet e calcula métricas completas por tópico e por habitante."""
    pqs = sorted(glob.glob(str(parquet_dir / "data" / "raw" / "disque100-*.parquet"))) or sorted(glob.glob(str(parquet_dir / "disque100-*.parquet")))
    print(f"Processando {len(pqs)} arquivos Parquet do Disque 100 para SC...")

    code_to_meta = {}
    name_to_code = {}
    for row in df_ibge_sc.to_dicts():
        cid = str(row["municipio-id"])
        cname = str(row["municipio-nome"]).strip().upper()
        code_to_meta[cid] = row
        name_to_code[cname] = cid

    total_sc_rows = 0
    by_year: Dict[str, int] = {}
    by_topic_counts: Dict[str, int] = {k: 0 for k in TOPICS_MAP}
    by_mun_data: Dict[str, Dict[str, Any]] = {}

    kpi_candidates = [
        parquet_dir / "data" / "processed" / "sc_kpis_grupos_municipios.csv",
        parquet_dir / "sc_kpis_grupos_municipios.csv"
    ]
    kpi_file = next((p for p in kpi_candidates if p.exists()), None)
    if kpi_file and kpi_file.exists():
        print(f"Carregando dados pré-processados e auditados de {kpi_file.name}...")
        df_kpi = pl.read_csv(kpi_file)
        json_candidates = [
            parquet_dir / "data" / "processed" / "sc_distribuicao_penal_metricas.json",
            parquet_dir / "sc_distribuicao_penal_metricas.json"
        ]
        json_file = next((p for p in json_candidates if p.exists()), None)
        by_year = {}
        if json_file and json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    d_m = json.load(f)
                    by_year = {ano: d_m["por_ano"][ano]["total"] for ano in d_m["por_ano"]}
            except Exception:
                pass

        total_sc_rows = 0
        # Carrega dados anuais detalhados para filtros dinâmicos por ano/período
        ano_candidates = [
            parquet_dir / "data" / "processed" / "sc_kpis_grupos_municipios_ano.parquet",
            parquet_dir / "sc_kpis_grupos_municipios_ano.parquet"
        ]
        ano_file = next((p for p in ano_candidates if p.exists()), None)
        ano_by_mun = {}
        if ano_file and ano_file.exists():
            try:
                df_ano_pl = pl.read_parquet(ano_file)
                for ra in df_ano_pl.to_dicts():
                    c_id = str(ra["ibge_code"])
                    a_str = str(ra["ano"])
                    if c_id not in ano_by_mun:
                        ano_by_mun[c_id] = {}
                    ano_by_mun[c_id][a_str] = {
                        "total": [int(ra.get("total_denuncias", 0)), int(ra.get("total_penal", 0))],
                        "crianca": [int(ra.get("criancas_total", 0)), int(ra.get("criancas_penal", 0))],
                        "mulher": [int(ra.get("mulheres_total", 0)), int(ra.get("mulheres_penal", 0))],
                        "idoso": [int(ra.get("idosos_total", 0)), int(ra.get("idosos_penal", 0))],
                        "pcd": [int(ra.get("pcd_total", 0)), int(ra.get("pcd_penal", 0))],
                        "lgbt": [int(ra.get("lgbt_total", 0)), int(ra.get("lgbt_penal", 0))],
                        "preso": [int(ra.get("prisional_total", 0)), int(ra.get("prisional_penal", 0))]
                    }
            except Exception as e_ano:
                print(f"[!] Erro ao carregar dados anuais: {e_ano}")

        for r in df_kpi.to_dicts():
            cid = str(r["ibge_code"])
            pop = int(r["populacao_censo_2022"])
            tot_mun = int(r["total_denuncias"])
            total_sc_rows += tot_mun
            by_mun_data[cid] = {
                "ibge_code": cid,
                "ano_data": ano_by_mun.get(cid, {}),
                "nome": r["municipio"],
                "regiao_imediata": r["regiao_imediata"],
                "regiao_intermediaria": r["regiao_intermediaria"],
                "populacao": pop,
                "topics": {
                    "total": tot_mun,
                    "crianca": int(r["criancas_total"]),
                    "mulher": int(r["mulheres_total"]),
                    "idoso": int(r["idosos_total"]),
                    "pcd": int(r["pcd_total"]),
                    "lgbt": int(r["lgbt_total"]),
                    "preso": int(r["prisional_total"])
                },
                "topics_detail": {
                    "total": {
                        "total": tot_mun,
                        "penal": int(r.get("total_penal", 0)),
                        "social": int(r.get("total_social", max(0, tot_mun - int(r.get("total_penal", 0)))))
                    },
                    "crianca": {
                        "total": int(r.get("criancas_total", 0)),
                        "penal": int(r.get("criancas_penal", 0)),
                        "social": max(0, int(r.get("criancas_total", 0)) - int(r.get("criancas_penal", 0)))
                    },
                    "mulher": {
                        "total": int(r.get("mulheres_total", 0)),
                        "penal": int(r.get("mulheres_penal", 0)),
                        "social": max(0, int(r.get("mulheres_total", 0)) - int(r.get("mulheres_penal", 0)))
                    },
                    "idoso": {
                        "total": int(r.get("idosos_total", 0)),
                        "penal": int(r.get("idosos_penal", 0)),
                        "social": max(0, int(r.get("idosos_total", 0)) - int(r.get("idosos_penal", 0)))
                    },
                    "pcd": {
                        "total": int(r.get("pcd_total", 0)),
                        "penal": int(r.get("pcd_penal", 0)),
                        "social": max(0, int(r.get("pcd_total", 0)) - int(r.get("pcd_penal", 0)))
                    },
                    "lgbt": {
                        "total": int(r.get("lgbt_total", 0)),
                        "penal": int(r.get("lgbt_penal", 0)),
                        "social": max(0, int(r.get("lgbt_total", 0)) - int(r.get("lgbt_penal", 0)))
                    },
                    "preso": {
                        "total": int(r.get("prisional_total", 0)),
                        "penal": int(r.get("prisional_penal", 0)),
                        "social": max(0, int(r.get("prisional_total", 0)) - int(r.get("prisional_penal", 0)))
                    }
                }
            }

        for top_key in TOPICS_MAP:
            by_topic_counts[top_key] = sum(m["topics"].get(top_key, 0) for m in by_mun_data.values())

        reg_data = {}
        for cid, mdata in by_mun_data.items():
            rname = mdata["regiao_intermediaria"]
            if rname not in reg_data:
                meta_r = REGION_METADATA.get(rname, {
                    "pci_superintendencias": [],
                    "pci_nucleos": [],
                    "pci_total_unidades": 0,
                    "rodovias_principais": ["BR-101", "BR-282"]
                })
                reg_data[rname] = {
                    "nome": rname,
                    "populacao": 0,
                    "pci_superintendencias": meta_r["pci_superintendencias"],
                    "pci_nucleos": meta_r["pci_nucleos"],
                    "pci_total_unidades": meta_r["pci_total_unidades"],
                    "rodovias_principais": meta_r["rodovias_principais"],
                    "topics": {k: 0 for k in TOPICS_MAP}
                }
            reg_data[rname]["populacao"] += mdata["populacao"]
            for top_key, val in mdata["topics"].items():
                reg_data[rname]["topics"][top_key] += val

        return {
            "total_sc": total_sc_rows,
            "by_year": by_year,
            "by_topic_counts": by_topic_counts,
            "by_mun_data": by_mun_data,
            "reg_data": reg_data,
            "pop_map": pop_map
        }

    for cid, meta in code_to_meta.items():
        pop = pop_map.get(cid, 10000)
        by_mun_data[cid] = {
            "ibge_code": cid,
            "nome": meta["municipio-nome"],
            "regiao_imediata": meta["regiao-imediata-nome"],
            "regiao_intermediaria": meta["regiao-intermediaria-nome"],
            "populacao": pop,
            "topics": {k: 0 for k in TOPICS_MAP}
        }

    for p in pqs:
        m_ano = re.search(r"20\d\d", os.path.basename(p))
        ano = m_ano.group(0) if m_ano else "2026"

        df = pl.read_parquet(p)
        cols = df.columns

        uf_col = None
        mun_col = None
        grp_col = None

        if "vitima_uf" in cols:
            uf_col = "vitima_uf"
            mun_col = "vitima_cod_municipio" if "vitima_cod_municipio" in cols else "vitima_municipio"
            grp_col = "grupo_violacao" if "grupo_violacao" in cols else None
        elif "UF" in cols:
            uf_col = "UF"
            mun_col = "Município" if "Município" in cols else "sl_vitima_naturalizado_municipio"
            grp_col = "Grupo_vulnerável" if "Grupo_vulnerável" in cols else "Grupo vulnerável"

        if not uf_col and "UF da vítima" in cols:
            uf_col = "UF da vítima"
        if not grp_col and "violacao" in cols:
            grp_col = "violacao"

        df_sc = None
        if uf_col and uf_col in cols:
            df_sc = df.filter(pl.col(uf_col).cast(pl.Utf8).str.to_uppercase() == "SC")
        elif mun_col and mun_col in cols:
            df_sc = df.filter(pl.col(mun_col).cast(pl.Utf8).str.starts_with("42"))

        if df_sc is None or len(df_sc) == 0:
            continue

        cnt = len(df_sc)
        total_sc_rows += cnt
        by_year[ano] = by_year.get(ano, 0) + cnt

        select_cols = []
        if mun_col and mun_col in df_sc.columns:
            select_cols.append(pl.col(mun_col).cast(pl.Utf8).alias("raw_mun"))
        else:
            select_cols.append(pl.lit(None, dtype=pl.Utf8).alias("raw_mun"))

        if grp_col and grp_col in df_sc.columns:
            select_cols.append(pl.col(grp_col).cast(pl.Utf8).alias("raw_grp"))
        else:
            select_cols.append(pl.lit("Outros", dtype=pl.Utf8).alias("raw_grp"))

        extracted = df_sc.select(select_cols).to_dicts()

        for rec in extracted:
            raw_m = rec["raw_mun"]
            raw_g = rec["raw_grp"]
            top_key = classify_topic(raw_g)
            by_topic_counts[top_key] += 1
            by_topic_counts["total"] += 1

            cid = None
            if raw_m:
                raw_m_str = str(raw_m).strip()
                if len(raw_m_str) >= 7 and raw_m_str[:7].isdigit() and raw_m_str.startswith("42"):
                    cid = raw_m_str[:7]
                elif raw_m_str.isdigit() and raw_m_str.startswith("42"):
                    cid = raw_m_str
                else:
                    norm_m = raw_m_str.upper()
                    if norm_m in name_to_code:
                        cid = name_to_code[norm_m]

            if cid and cid in by_mun_data:
                by_mun_data[cid]["topics"][top_key] += 1
                by_mun_data[cid]["topics"]["total"] += 1

    # Agregação por Região Intermediária
    reg_data: Dict[str, Dict[str, Any]] = {}
    for cid, mdata in by_mun_data.items():
        rname = mdata["regiao_intermediaria"]
        if rname not in reg_data:
            meta_r = REGION_METADATA.get(rname, {
                "pci_superintendencias": [],
                "pci_nucleos": [],
                "pci_total_unidades": 0,
                "rodovias_principais": ["BR-101", "BR-282"]
            })
            reg_data[rname] = {
                "nome": rname,
                "populacao": 0,
                "pci_superintendencias": meta_r["pci_superintendencias"],
                "pci_nucleos": meta_r["pci_nucleos"],
                "pci_total_unidades": meta_r["pci_total_unidades"],
                "rodovias_principais": meta_r["rodovias_principais"],
                "topics": {k: 0 for k in TOPICS_MAP}
            }
        reg_data[rname]["populacao"] += mdata["populacao"]
        for top_key, val in mdata["topics"].items():
            reg_data[rname]["topics"][top_key] += val

    return {
        "total_sc": total_sc_rows,
        "by_year": by_year,
        "by_topic_counts": by_topic_counts,
        "by_mun_data": by_mun_data,
        "reg_data": reg_data,
        "pop_map": pop_map
    }


def compute_peaks_and_centroids(
    sc_data: Dict[str, Any],
    geojson_sc: Dict[str, Any],
    pci_units: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calcula centróides geográficos para todos os municípios e identifica os 10 pontos
    de pico para cada tipo de incidente com proporção referenciada a cada 10k de habitantes.
    Identifica também a concentração espacial e clusters regionais dos picos.
    """
    print("Identificando centróides geográficos e os 10 pontos de pico por tipo de incidente (proporção / 10k hab)...")
    centroids = {}
    for f in geojson_sc["features"]:
        cid = str(f["properties"]["codarea"])
        lat, lng = get_feature_centroid(f)
        centroids[cid] = {"lat": round(lat, 5), "lng": round(lng, 5)}

    by_mun_data = sc_data["by_mun_data"]
    for cid, m in by_mun_data.items():
        coords = centroids.get(cid, {"lat": -27.24, "lng": -50.21})
        m["lat"] = coords["lat"]
        m["lng"] = coords["lng"]
        if pci_units:
            closest_pci = min(pci_units, key=lambda u: haversine_km(coords["lat"], coords["lng"], u["latitude"], u["longitude"]))
            dist_km = haversine_km(coords["lat"], coords["lng"], closest_pci["latitude"], closest_pci["longitude"])
            m["pci_proxima"] = f"{closest_pci['nome_unidade']} ({dist_km:.1f} km)"
        else:
            m["pci_proxima"] = "PCI SC Regional"

    peaks_by_topic = {}

    for top_key, top_name in TOPICS_MAP.items():
        candidates = []
        for cid, m in by_mun_data.items():
            tot = m["topics"].get(top_key, 0)
            pop = m.get("populacao", 10000)
            # Proporção por 10 mil habitantes (conforme solicitado pelo usuário)
            tot_10k = (tot / pop * 10000.0) if pop > 0 else 0.0
            media_anual = tot / 16.0
            taxa_anual_10k = (media_anual / pop * 10000.0) if pop > 0 else 0.0
            coords = centroids.get(cid, {"lat": -27.24, "lng": -50.21})

            candidates.append({
                "code": cid,
                "nome": m["nome"],
                "regiao": m["regiao_intermediaria"],
                "pop": pop,
                "total": tot,
                "total_10k": round(tot_10k, 2),
                "media_anual": round(media_anual, 2),
                "taxa_anual_10k": round(taxa_anual_10k, 2),
                "lat": coords["lat"],
                "lng": coords["lng"]
            })

        # Ordena estritamente pela proporção de pico: total de casos a cada 10k habitantes
        candidates.sort(key=lambda x: x["total_10k"], reverse=True)
        top10 = candidates[:10]

        # Identifica concentração geográfica regional dos 10 picos
        reg_counts = {}
        for c in top10:
            reg_counts[c["regiao"]] = reg_counts.get(c["regiao"], 0) + 1
        sorted_regs = sorted(reg_counts.items(), key=lambda x: x[1], reverse=True)
        concentration_desc = ", ".join([f"{cnt} na Região de {r}" for r, cnt in sorted_regs])

        # Agrupamentos (clusters) espaciais onde há 2 ou mais picos na mesma região
        clusters = []
        for rname, count in sorted_regs:
            if count >= 2:
                reg_peaks = [c for c in top10 if c["regiao"] == rname]
                c_lat = sum(p["lat"] for p in reg_peaks) / len(reg_peaks)
                c_lng = sum(p["lng"] for p in reg_peaks) / len(reg_peaks)
                clusters.append({
                    "regiao": rname,
                    "count": count,
                    "lat": round(c_lat, 5),
                    "lng": round(c_lng, 5),
                    "muns": [p["nome"] for p in reg_peaks]
                })

        # Enriquecimento dos 10 pontos de pico com PCI mais próxima e rodovias principais
        enriched_top10 = []
        for idx, item in enumerate(top10):
            ilat, ilng = item["lat"], item["lng"]
            if pci_units:
                closest_pci = min(pci_units, key=lambda u: haversine_km(ilat, ilng, u["latitude"], u["longitude"]))
                dist_km = haversine_km(ilat, ilng, closest_pci["latitude"], closest_pci["longitude"])
                pci_desc = f"{closest_pci['nome_unidade']} ({dist_km:.1f} km)"
            else:
                pci_desc = "Atendimento regional descentralizado"

            reg_meta = REGION_METADATA.get(item["regiao"], {})
            rodovias = reg_meta.get("rodovias_principais", ["BR-101", "BR-282"])

            enriched_top10.append({
                "rank": idx + 1,
                "code": item["code"],
                "nome": item["nome"],
                "regiao": item["regiao"],
                "pop": item["pop"],
                "total": item["total"],
                "total_10k": item["total_10k"],
                "media_anual": item["media_anual"],
                "taxa_anual_10k": item["taxa_anual_10k"],
                "lat": item["lat"],
                "lng": item["lng"],
                "icon": TOPIC_ICONS.get(top_key, ""),
                "pci_proxima": pci_desc,
                "rodovias": rodovias[:4],
                "regional_concentration": concentration_desc
            })

        peaks_by_topic[top_key] = {
            "top10": enriched_top10,
            "concentration": concentration_desc,
            "regional_distribution": dict(sorted_regs),
            "clusters": clusters
        }

    return {
        "centroids": centroids,
        "peaks_by_topic": peaks_by_topic
    }


def build_roads_geojson() -> List[Dict[str, Any]]:
    """
    Eixos rodoviarios de referencia, definidos em `scripts/eixos_rodoviarios_sc.py`.

    A definicao saiu deste arquivo para um modulo proprio, de modo que o painel
    Streamlit e este mapa pre-gerado desenhem exatamente os mesmos eixos. Os
    tracados sao esquematicos, e nao a geometria oficial do DNIT ou do DEINFRA.
    """
    from eixos_rodoviarios_sc import eixos_como_geojson

    return eixos_como_geojson()


def generate_interactive_dashboard(
    sc_data: Dict[str, Any],
    pci_units: List[Dict[str, Any]],
    geojson_sc: Dict[str, Any],
    geojson_inter: Dict[str, Any],
    peaks_info: Dict[str, Any],
    output_path: Path
):
    """Gera o dashboard Folium dinâmico com reatividade client-side via Leaflet/JS."""
    print("Montando Dashboard Dinâmico em Folium com Camada de Pontos de Pico...")

    by_mun_data = sc_data["by_mun_data"]
    reg_data = sc_data["reg_data"]
    pop_map = sc_data["pop_map"]
    by_year = sc_data["by_year"]
    by_topic_counts = sc_data["by_topic_counts"]
    total_sc = sc_data["total_sc"]
    total_pop_sc = sum(pop_map.values())
    roads = build_roads_geojson()

    # Prepara atributos enriquecidos nos GeoJSONs
    for f in geojson_sc["features"]:
        cid = str(f["properties"]["codarea"])
        m = by_mun_data.get(cid, {})
        f["properties"]["data"] = m

    for f in geojson_inter["features"]:
        cid = str(f["properties"]["codarea"])
        reg_names_map = {
            "4201": "Florianópolis", "4202": "Criciúma", "4203": "Lages",
            "4204": "Chapecó", "4205": "Caçador", "4206": "Joinville", "4207": "Blumenau"
        }
        rname = reg_names_map.get(cid, f"Região {cid}")
        r = reg_data.get(rname, {"nome": rname, "populacao": 100000, "topics": {k: 0 for k in TOPICS_MAP}})
        f["properties"]["data"] = r

    # Mapa Base Folium (SVG nativo para interatividade perfeita de DOM/hover)
    m = folium.Map(
        location=[-27.24, -50.21],
        zoom_start=8,
        tiles="OpenStreetMap",
        control_scale=True,
        prefer_canvas=False
    )
    map_var_name = m.get_name()

    # Injeção de CSS e JavaScript para o Motor Reativo do Leaflet
    app_payload = {
        "geojson_mun": geojson_sc,
        "geojson_inter": geojson_inter,
        "pci_units": pci_units,
        "roads": roads,
        "topics_map": TOPICS_MAP,
        "topic_icons": TOPIC_ICONS,
        "peaks_by_topic": peaks_info["peaks_by_topic"],
        "reg_data": reg_data,
        "by_year": by_year,
        "by_topic_counts": by_topic_counts,
        "total_sc": total_sc,
        "total_pop_sc": total_pop_sc
    }

    embedded_html = f"""
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <!-- Estilos Refinados dos Tooltips, Marcadores de Pico e Panes -->
    <style>
        .leaflet-pane {{
            pointer-events: none !important;
        }}
        .leaflet-pane.leaflet-map-pane {{
            pointer-events: auto !important;
        }}
        .leaflet-interactive {{
            pointer-events: auto !important;
            cursor: pointer !important;
        }}
        .leaflet-pane.leaflet-tooltip-pane {{
            z-index: 10000 !important;
            pointer-events: none !important;
        }}
        .leaflet-pane.leaflet-popup-pane {{
            z-index: 10050 !important;
        }}
        .leaflet-tooltip.custom-sc-tooltip {{
            background: rgba(15, 23, 42, 0.96) !important;
            border: 1px solid rgba(56, 189, 248, 0.5) !important;
            border-radius: 12px !important;
            color: #f8fafc !important;
            box-shadow: 0 15px 35px rgba(0, 0, 0, 0.7) !important;
            padding: 10px 14px !important;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif !important;
            backdrop-filter: blur(10px) !important;
            -webkit-backdrop-filter: blur(10px) !important;
            pointer-events: none !important;
            z-index: 9999 !important;
            z-index: 10001 !important;
            max-width: 330px !important;
        }}
        .leaflet-tooltip.custom-sc-tooltip:before {{
            border-top-color: rgba(15, 23, 42, 0.96) !important;
            border-bottom-color: rgba(15, 23, 42, 0.96) !important;
            border-left-color: rgba(15, 23, 42, 0.96) !important;
            border-right-color: rgba(15, 23, 42, 0.96) !important;
        }}
        .peak-pulse-glow {{
            pointer-events: none !important;
        }}

        /* Animações e Marcadores dos Pontos de Pico */
        @keyframes peakRadarPulse {{
            0% {{
                transform: scale(0.8);
                opacity: 0.95;
            }}
            70% {{
                transform: scale(1.7);
                opacity: 0;
            }}
            100% {{
                transform: scale(1.7);
                opacity: 0;
            }}
        }}

        .peak-marker-wrapper {{
            position: relative;
            width: 44px;
            height: 44px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer !important;
            transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
        }}
        .peak-marker-wrapper:hover {{
            transform: scale(1.22);
            z-index: 9999 !important;
        }}
        .peak-pulse-glow {{
            position: absolute;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            pointer-events: none;
            animation: peakRadarPulse 2.2s infinite cubic-bezier(0.215, 0.61, 0.355, 1);
        }}
        .peak-badge-icon {{
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #ffffff;
            box-shadow: 0 4px 14px rgba(0,0,0,0.65);
            font-size: 15px;
            z-index: 2;
            user-select: none;
        }}
        .peak-rank-tag {{
            position: absolute;
            top: -4px;
            right: -2px;
            border: 1.5px solid #ffffff;
            border-radius: 10px;
            font-size: 9px;
            font-weight: 800;
            padding: 1px 5px;
            line-height: 1.2;
            box-shadow: 0 2px 6px rgba(0,0,0,0.6);
            z-index: 3;
            user-select: none;
        }}

        .peak-list-row {{
            background: rgba(15, 23, 42, 0.65);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            padding: 7px 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        .peak-list-row:hover {{
            background: rgba(2, 132, 199, 0.25);
            border-color: rgba(245, 158, 11, 0.6);
            transform: translateX(3px);
        }}
    </style>

    <!-- Dados Estruturados em JSON -->
    <script>
        window.SC_DASHBOARD_DATA = {json.dumps(app_payload, ensure_ascii=False)};
        window.FOLIUM_MAP_VAR_NAME = "{map_var_name}";
    </script>

    <!-- Botão de Minimizar / Expandir Painel (Oculto: filtros centralizados no Streamlit) -->
    <button id="toggle-panel-btn" onclick="toggleDashboardPanel()" style="
        display: none !important;
        position: fixed;
        top: 16px;
        left: 16px;
        z-index: 9999;
        background: linear-gradient(135deg, #0284c7, #0369a1);
        color: #ffffff;
        border: 1px solid rgba(255,255,255,0.2);
        padding: 10px 18px;
        border-radius: 12px;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        font-size: 13px;
        font-weight: 700;
        box-shadow: 0 10px 25px rgba(0,0,0,0.4);
        cursor: pointer;
        align-items: center;
        gap: 8px;
        backdrop-filter: blur(8px);
        transition: all 0.2s ease;
    ">
        <span>Painel de Filtros & Métricas</span>
        <span id="panel-toggle-icon">◀</span>
    </button>

    <!-- Controles Rápidos Diretos no Mapa (Clusters, Picos, PCI, Rodovias) -->
    <div id="map-quick-controls" style="
        position: fixed;
        top: 16px;
        right: 16px;
        z-index: 9999;
        background: rgba(15, 23, 42, 0.90);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.16);
        border-radius: 12px;
        padding: 12px 16px;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 11.5px;
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.45);
        min-width: 220px;
    ">
        <div style="font-weight: 800; color: #38bdf8; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
            <span>Camadas no Mapa</span>
            <span id="cluster-count-badge" style="background: rgba(245, 158, 11, 0.25); color: #fbbf24; padding: 1px 6px; border-radius: 8px; font-size: 9px; font-weight: 700;">Ativo</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 6px;">
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-weight: 600;">
                <input type="checkbox" id="chk-direct-clusters" checked onchange="toggleMapClusters(this.checked)" style="accent-color: #f59e0b; width: 14px; height: 14px; cursor: pointer;">
                <span style="color: #fbbf24;">Clusters de Concentração</span>
            </label>
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: #cbd5e1;">
                <input type="checkbox" id="chk-direct-peaks" checked onchange="toggleMapPeaks(this.checked)" style="accent-color: #ef4444; width: 14px; height: 14px; cursor: pointer;">
                <span>Top 10 Pontos de Pico</span>
            </label>
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: #cbd5e1;">
                <input type="checkbox" id="chk-direct-pci" checked onchange="togglePCILayer(this.checked)" style="accent-color: #38bdf8; width: 14px; height: 14px; cursor: pointer;">
                <span>Polícia Científica (PCI)</span>
            </label>
            <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; color: #cbd5e1;">
                <input type="checkbox" id="chk-direct-roads" checked onchange="toggleRoadsLayer(this.checked)" style="accent-color: #94a3b8; width: 14px; height: 14px; cursor: pointer;">
                <span>Rodovias Principais</span>
            </label>
        </div>
    </div>

    <!-- Legenda Dinâmica Flutuante -->
    <div id="dynamic-legend" style="
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9999;
        background: rgba(15, 23, 42, 0.92);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 14px;
        padding: 14px 18px;
        color: #ffffff;
        font-family: 'Segoe UI', system-ui, sans-serif;
        font-size: 11px;
        box-shadow: 0 15px 30px rgba(0,0,0,0.5);
        min-width: 260px;
    ">
        <div id="legend-title" style="font-weight: 700; color: #38bdf8; margin-bottom: 8px;">Total a cada 10k hab</div>
        <div style="display: flex; height: 12px; border-radius: 6px; overflow: hidden; margin-bottom: 6px; background: linear-gradient(to right, #93c5fd, #60a5fa, #2563eb, #1e3a8a);"></div>
        <div style="display: flex; justify-content: space-between; font-size: 10px; color: #cbd5e1;">
            <span id="legend-min">0,0</span>
            <span id="legend-mid">--</span>
            <span id="legend-max">--</span>
        </div>
    </div>

    <!-- Painel Lateral Glassmorphism (Oculto: controles no Streamlit) -->
    <div id="sc-dashboard-panel" style="
        display: none !important;
        position: fixed;
        top: 16px;
        left: 16px;
        width: 480px;
        max-width: calc(100vw - 32px);
        max-height: calc(100vh - 32px);
        overflow-y: auto;
        z-index: 9998;
        background: rgba(15, 23, 42, 0.94);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 20px;
        padding: 24px 20px;
        color: #f8fafc;
        font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
        transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
    ">
        <!-- Header -->
        <div style="margin-bottom: 16px; padding-top: 36px;">
            <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px;">
                <span style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700;">SANTA CATARINA (SC)</span>
                <span style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: 700;">PONTOS DE PICO / 10K HAB</span>
            </div>
            <h1 style="margin: 0; font-size: 19px; font-weight: 800; color: #ffffff;">Disque 100 & Picos Territoriais</h1>
            <p style="margin: 3px 0 0 0; font-size: 11px; color: #94a3b8;">Concentrações espaciais, 10 picos por categoria e Polícia Científica</p>
        </div>

        <!-- ================================================================= -->
        <!-- CONTROLES E FILTROS DINÂMICOS -->
        <!-- ================================================================= -->
        <div style="background: rgba(30, 41, 59, 0.85); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 14px; margin-bottom: 16px;">
            <div style="font-size: 11px; font-weight: 700; color: #38bdf8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;">Controles & Filtros Interativos</div>

            <!-- 1. Filtro de Nível Territorial -->
            <div style="margin-bottom: 12px;">
                <label style="font-size: 11px; color: #94a3b8; font-weight: 600; display: block; margin-bottom: 4px;">Nível Territorial:</label>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px;">
                    <button id="btn-geo-mun" onclick="setGeoLevel('mun')" style="padding: 7px 4px; background: #0284c7; color: white; border: none; border-radius: 8px; font-size: 11px; font-weight: 700; cursor: pointer;">Municípios</button>
                    <button id="btn-geo-reg" onclick="setGeoLevel('reg')" style="padding: 7px 4px; background: #1e293b; color: #cbd5e1; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; font-size: 11px; font-weight: 600; cursor: pointer;">Regiões</button>
                    <button id="btn-geo-both" onclick="setGeoLevel('both')" style="padding: 7px 4px; background: #1e293b; color: #cbd5e1; border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; font-size: 11px; font-weight: 600; cursor: pointer;">Ambos</button>
                </div>
            </div>

            <!-- 2. Filtro de Métrica -->
            <div style="margin-bottom: 12px;">
                <label style="font-size: 11px; color: #94a3b8; font-weight: 600; display: block; margin-bottom: 4px;">Métrica de Análise:</label>
                <select id="select-metric" onchange="updateDashboardView()" style="width: 100%; background: #0f172a; color: #f8fafc; border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; padding: 8px 10px; font-size: 12px; font-weight: 600; cursor: pointer; outline: none;">
                    <option value="total_10k" selected>Proporção: Total a cada 10k hab (Referência de Picos)</option>
                    <option value="taxa_anual_10k">Taxa Anual por 10k Habitantes</option>
                    <option value="taxa_anual_100k">Taxa Anual por 100k Habitantes (Censo 2022)</option>
                    <option value="total">Total Histórico Acumulado (2011–2026)</option>
                    <option value="media_anual">Média anual de registros de violação</option>
                </select>
            </div>

            <!-- 3. Filtro de Tipo de Incidente / Tópico -->
            <div style="margin-bottom: 12px;">
                <label style="font-size: 11px; color: #94a3b8; font-weight: 600; display: block; margin-bottom: 4px;">Tipo de Incidente / Grupo Vulnerável:</label>
                <select id="select-topic" onchange="updateDashboardView()" style="width: 100%; background: #0f172a; color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 8px 10px; font-size: 12px; font-weight: 700; cursor: pointer; outline: none;">
                    <option value="total">Todos os Incidentes (Visão Geral)</option>
                    <option value="crianca">Crianças e Adolescentes (ECA)</option>
                    <option value="mulher">Mulheres (Violência de Gênero)</option>
                    <option value="idoso">Pessoas Idosas (Estatuto do Idoso)</option>
                    <option value="pcd">Pessoas com Deficiência (PCD)</option>
                    <option value="lgbt">População LGBTQIA+</option>
                    <option value="preso">Sistema Prisional e Situação de Rua</option>
                </select>
            </div>

            <!-- 4. Camadas em Destaque (Picos, PCI e Rodovias) -->
            <div>
                <label style="font-size: 11px; color: #94a3b8; font-weight: 600; display: block; margin-bottom: 6px;">Camadas em Destaque (Prioridade Visual):</label>
                <div style="display: flex; flex-wrap: wrap; gap: 10px;">
                    <label style="font-size: 11px; display: flex; align-items: center; gap: 6px; cursor: pointer; color: #fbbf24; font-weight: 700;">
                        <input type="checkbox" id="chk-peaks" checked onchange="togglePeaksLayer(this.checked)">
                        <span>10 Pontos de Pico (10k hab)</span>
                    </label>
                    <label style="font-size: 11px; display: flex; align-items: center; gap: 6px; cursor: pointer; color: #e2e8f0;">
                        <input type="checkbox" id="chk-pci" checked onchange="togglePCILayer(this.checked)">
                        <span>30 Unidades PCI-SC</span>
                    </label>
                    <label style="font-size: 11px; display: flex; align-items: center; gap: 6px; cursor: pointer; color: #e2e8f0;">
                        <input type="checkbox" id="chk-roads" checked onchange="toggleRoadsLayer(this.checked)">
                        <span>Rodovias</span>
                    </label>
                </div>
            </div>
        </div>

        <!-- ================================================================= -->
        <!-- SEÇÃO: 10 PONTOS DE PICO POR CATEGORIA (REFERÊNCIA: 10K HABITANTES) -->
        <!-- ================================================================= -->
        <div style="background: rgba(30, 41, 59, 0.85); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 16px; padding: 14px; margin-bottom: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.3);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <div style="font-size: 12px; font-weight: 800; color: #fbbf24; display: flex; align-items: center; gap: 6px;">
                    <span></span>
                    <span>Top 10 Pontos de Pico (por 10k hab)</span>
                </div>
                <span id="peaks-badge-topic" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-size: 10px; font-weight: 800; padding: 2px 8px; border-radius: 12px; border: 1px solid rgba(245, 158, 11, 0.4);">
                    Todos os Incidentes
                </span>
            </div>
            <div style="font-size: 10px; color: #94a3b8; margin-bottom: 8px;">
                Referência proporcional: <strong>total de casos a cada 10 mil habitantes</strong> (Censo 2022). Clique em qualquer pico para centralizar o mapa.
            </div>

            <!-- Card de Concentração Geográfica dos Picos -->
            <div id="peaks-concentration-box" style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; padding: 8px 10px; margin-bottom: 10px;">
                <div style="font-size: 10px; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 4px; margin-bottom: 3px;">
                    <span></span>
                    <span>Concentração Geográfica dos 10 Picos:</span>
                </div>
                <div id="peaks-concentration-text" style="font-size: 10px; color: #f1f5f9; line-height: 1.4;">
                    Carregando análise espacial...
                </div>
            </div>

            <!-- Lista interativa dos 10 Pontos de Pico -->
            <div id="peaks-items-list" style="display: flex; flex-direction: column; gap: 6px; max-height: 250px; overflow-y: auto; padding-right: 2px;">
            </div>
        </div>

        <!-- ================================================================= -->
        <!-- CARDS DE TOTAIS E KPIS DINÂMICOS -->
        <!-- ================================================================= -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px;">
            <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px;">
                <div style="font-size: 10px; color: #94a3b8; font-weight: 600;">Total Filtrado (SC)</div>
                <div id="kpi-total-filtrado" style="font-size: 20px; font-weight: 800; color: #38bdf8; margin-top: 2px;">--</div>
                <div id="kpi-total-sub" style="font-size: 10px; color: #cbd5e1; margin-top: 2px;">Todos os Incidentes</div>
            </div>
            <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px;">
                <div id="kpi-label-taxa-media" style="font-size: 10px; color: #94a3b8; font-weight: 600;">Taxa Média Estadual</div>
                <div id="kpi-taxa-media" style="font-size: 20px; font-weight: 800; color: #34d399; margin-top: 2px;">--</div>
                <div id="kpi-taxa-sub" style="font-size: 10px; color: #cbd5e1; margin-top: 2px;">Total a cada 10k hab</div>
            </div>
            <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px;">
                <div id="kpi-label-lider-rate" style="font-size: 10px; color: #94a3b8; font-weight: 600;">Líder Proporcional (/ 10k hab)</div>
                <div id="kpi-lider-rate" style="font-size: 13px; font-weight: 800; color: #f59e0b; margin-top: 3px;">--</div>
                <div id="kpi-lider-rate-sub" style="font-size: 10px; color: #cbd5e1; margin-top: 2px;">--</div>
            </div>
            <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 12px;">
                <div id="kpi-label-lider-tot" style="font-size: 10px; color: #94a3b8; font-weight: 600;">Líder em Volume Absoluto</div>
                <div id="kpi-lider-tot" style="font-size: 13px; font-weight: 800; color: #c084fc; margin-top: 3px;">--</div>
                <div id="kpi-lider-tot-sub" style="font-size: 10px; color: #cbd5e1; margin-top: 2px;">--</div>
            </div>
        </div>

        <!-- Seção: Tabela Dinâmica de Ranking -->
        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 14px; margin-bottom: 16px;">
            <div id="ranking-table-title" style="font-size: 12px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Ranking Territorial</div>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 11px;">
                    <thead id="ranking-table-head">
                    </thead>
                    <tbody id="ranking-table-body">
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Seção: Gráfico de Evolução Anual -->
        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 14px; margin-bottom: 16px;">
            <div style="font-size: 12px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">Evolução anual de registros de violação em SC</div>
            <div style="height: 140px; width: 100%;">
                <canvas id="scYearChart"></canvas>
            </div>
        </div>

        <!-- Seção: 30 Unidades da Polícia Científica -->
        <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 16px; padding: 14px;">
            <div style="font-size: 12px; font-weight: 700; color: #ffffff; margin-bottom: 8px;">30 Unidades da Polícia Científica de SC (PCI-SC)</div>
            <div id="pci-units-list" style="max-height: 200px; overflow-y: auto; padding-right: 4px;">
            </div>
        </div>
    </div>

    <!-- Script do Motor Dinâmico Leaflet -->
    <script>
        let currentGeoLevel = 'mun'; // 'mun', 'reg', 'both'
        let munLayerGroup = null;
        let regLayerGroup = null;
        let pciLayerGroup = null;
        let roadsLayerGroup = null;
        let peaksLayerGroup = null;
        let peaksConcentrationLayerGroup = null;
        let peakMarkersLookup = {{}};
        let leafletMapInstance = null;

        const numFmt = new Intl.NumberFormat('pt-BR');
        const decFmt = new Intl.NumberFormat('pt-BR', {{ minimumFractionDigits: 1, maximumFractionDigits: 1 }});

        function toggleDashboardPanel() {{
            const panel = document.getElementById('sc-dashboard-panel');
            const icon = document.getElementById('panel-toggle-icon');
            if (panel.style.transform === 'translateX(-520px)') {{
                panel.style.transform = 'translateX(0px)';
                panel.style.opacity = '1';
                icon.textContent = '◀';
            }} else {{
                panel.style.transform = 'translateX(-520px)';
                panel.style.opacity = '0';
                icon.textContent = '▶';
            }}
        }}

        function setGeoLevel(level) {{
            currentGeoLevel = level;
            const btnMun = document.getElementById('btn-geo-mun');
            const btnReg = document.getElementById('btn-geo-reg');
            const btnBoth = document.getElementById('btn-geo-both');

            if (btnMun) btnMun.style.background = (level === 'mun') ? '#0284c7' : '#1e293b';
            if (btnReg) btnReg.style.background = (level === 'reg') ? '#0284c7' : '#1e293b';
            if (btnBoth) btnBoth.style.background = (level === 'both') ? '#0284c7' : '#1e293b';

            if (btnMun) btnMun.style.color = (level === 'mun') ? '#ffffff' : '#cbd5e1';
            if (btnReg) btnReg.style.color = (level === 'reg') ? '#ffffff' : '#cbd5e1';
            if (btnBoth) btnBoth.style.color = (level === 'both') ? '#ffffff' : '#cbd5e1';

            updateDashboardView();
        }}

        function togglePCILayer(show) {{
            if (!leafletMapInstance || !pciLayerGroup) return;
            if (show) {{
                if (!leafletMapInstance.hasLayer(pciLayerGroup)) leafletMapInstance.addLayer(pciLayerGroup);
            }} else {{
                if (leafletMapInstance.hasLayer(pciLayerGroup)) leafletMapInstance.removeLayer(pciLayerGroup);
            }}
        }}

        function toggleRoadsLayer(show) {{
            if (!leafletMapInstance || !roadsLayerGroup) return;
            if (show) {{
                if (!leafletMapInstance.hasLayer(roadsLayerGroup)) leafletMapInstance.addLayer(roadsLayerGroup);
            }} else {{
                if (leafletMapInstance.hasLayer(roadsLayerGroup)) leafletMapInstance.removeLayer(roadsLayerGroup);
            }}
        }}

        let showClustersActive = true;
        let showPeaksActive = true;

        function toggleMapClusters(show) {{
            showClustersActive = !!show;
            const chk = document.getElementById('chk-direct-clusters');
            if (chk) chk.checked = showClustersActive;
            if (!leafletMapInstance || !peaksConcentrationLayerGroup) return;
            if (showClustersActive) {{
                if (!leafletMapInstance.hasLayer(peaksConcentrationLayerGroup)) {{
                    leafletMapInstance.addLayer(peaksConcentrationLayerGroup);
                }}
            }} else {{
                if (leafletMapInstance.hasLayer(peaksConcentrationLayerGroup)) {{
                    leafletMapInstance.removeLayer(peaksConcentrationLayerGroup);
                }}
            }}
        }}

        function toggleMapPeaks(show) {{
            showPeaksActive = !!show;
            const chk = document.getElementById('chk-direct-peaks');
            if (chk) chk.checked = showPeaksActive;
            if (!leafletMapInstance || !peaksLayerGroup) return;
            if (showPeaksActive) {{
                if (!leafletMapInstance.hasLayer(peaksLayerGroup)) {{
                    leafletMapInstance.addLayer(peaksLayerGroup);
                }}
            }} else {{
                if (leafletMapInstance.hasLayer(peaksLayerGroup)) {{
                    leafletMapInstance.removeLayer(peaksLayerGroup);
                }}
            }}
        }}

        function togglePeaksLayer(show) {{
            toggleMapPeaks(show);
            toggleMapClusters(show);
        }}

        function getMunTopicCounts(m, topicKey, yearParam) {{
            if (!yearParam || yearParam === 'all' || !m.ano_data || Object.keys(m.ano_data).length === 0) {{
                const tDetail = (m.topics_detail && m.topics_detail[topicKey]) ? m.topics_detail[topicKey] : null;
                if (tDetail) {{
                    return {{ total: tDetail.total, penal: tDetail.penal, social: tDetail.social }};
                }}
                const tot = (m.topics && m.topics[topicKey] !== undefined) ? m.topics[topicKey] : 0;
                return {{ total: tot, penal: Math.round(tot * 0.6125), social: Math.round(tot * 0.3875) }};
            }}

            let years = [];
            const yStr = String(yearParam).trim();
            if (yStr.includes('-')) {{
                const parts = yStr.split('-').map(Number);
                for (let y = parts[0]; y <= parts[1]; y++) years.push(String(y));
            }} else {{
                years.push(yStr);
            }}

            let sumTot = 0, sumPenal = 0;
            years.forEach(y => {{
                if (m.ano_data[y] && m.ano_data[y][topicKey]) {{
                    sumTot += m.ano_data[y][topicKey][0];
                    sumPenal += m.ano_data[y][topicKey][1];
                }}
            }});
            return {{ total: sumTot, penal: sumPenal, social: Math.max(0, sumTot - sumPenal) }};
        }}

        function flyToPeak(code, lat, lng) {{
            if (!leafletMapInstance) return;
            leafletMapInstance.flyTo([lat, lng], 11, {{
                duration: 1.2,
                easeLinearity: 0.25
            }});
            setTimeout(() => {{
                if (peakMarkersLookup && peakMarkersLookup[code]) {{
                    peakMarkersLookup[code].openPopup();
                }}
            }}, 1300);
        }}

        function getColorGradient(val, min, max) {{
            if (max <= min) return '#60a5fa';
            const t = Math.max(0, Math.min(1, (val - min) / (max - min)));
            const r = Math.round(147 + t * (30 - 147));
            const g = Math.round(197 + t * (58 - 197));
            const b = Math.round(253 + t * (138 - 253));
            return `rgb(${{r}}, ${{g}}, ${{b}})`;
        }}

        function computeMetricValue(topicsObj, pop, metricKey, topicKey) {{
            const count = (topicsObj && topicsObj[topicKey]) ? topicsObj[topicKey] : 0;
            if (metricKey === 'total') return count;
            if (metricKey === 'media_anual') return count / 16.0;
            if (metricKey === 'total_10k') {{
                return pop > 0 ? (count / pop * 10000.0) : 0;
            }}
            if (metricKey === 'taxa_anual_10k') {{
                const mediaAnual = count / 16.0;
                return pop > 0 ? (mediaAnual / pop * 10000.0) : 0;
            }}
            if (metricKey === 'taxa_anual_100k') {{
                const mediaAnual = count / 16.0;
                return pop > 0 ? (mediaAnual / pop * 100000.0) : 0;
            }}
            return count;
        }}

        function renderPeakMarkers(topicKey, metricType, scaleFactor, regionFilter, yearFilter) {{
            if (!leafletMapInstance || !peaksLayerGroup || !peaksConcentrationLayerGroup) return;
            const D = window.SC_DASHBOARD_DATA;
            if (!D) return;

            topicKey = topicKey || 'total';
            metricType = metricType || 'penal';
            scaleFactor = Number(scaleFactor) || 10000;
            regionFilter = regionFilter || 'all';

            peaksLayerGroup.clearLayers();
            peaksConcentrationLayerGroup.clearLayers();
            peakMarkersLookup = {{}};

            const topicLabels = {{
                'total': 'Visão Consolidada (Todos os Casos)',
                'crianca': 'Crianças e Adolescentes (ECA)',
                'mulher': 'Mulheres em Violência de Gênero',
                'idoso': 'Pessoas Idosas (Estatuto da Pessoa Idosa)',
                'pcd': 'Pessoas com Deficiência (PCD)',
                'lgbt': 'População LGBTQIA+',
                'preso': 'Sistema Prisional e População de Rua'
            }};
            const metricNames = {{
                'penal': 'Indício Penal',
                'social': 'Demanda Socioassistencial',
                'total': 'Total Geral'
            }};

            const topicLabel = topicLabels[topicKey] || (D.topics_map && D.topics_map[topicKey]) || 'Total Geral';
            const metricLabel = metricNames[metricType] || 'Indício Penal';
            const scaleLabel = (scaleFactor === 100000) ? '100k hab' : ((scaleFactor === 50000) ? '50k hab' : '10k hab');

            // 1. Calcula ranking dinâmico com base nos filtros ativos
            const candidates = [];
            if (D.geojson_mun && D.geojson_mun.features) {{
                D.geojson_mun.features.forEach(f => {{
                    const m = (f.properties && f.properties.data) ? f.properties.data : {{}};
                    if (!m.lat || !m.lng) return;
                    if (regionFilter !== 'all' && m.regiao_intermediaria !== regionFilter) return;

                    const pop = m.populacao || 10000;
                    const tDetail = (m.topics_detail && m.topics_detail[topicKey]) ? m.topics_detail[topicKey] : null;
                    let count = 0;
                    if (tDetail) {{
                        count = (tDetail[metricType] !== undefined) ? tDetail[metricType] : tDetail.total;
                    }} else if (m.topics && m.topics[topicKey] !== undefined) {{
                        const tot = m.topics[topicKey];
                        count = (metricType === 'penal') ? Math.round(tot * 0.6125) : ((metricType === 'social') ? Math.round(tot * 0.3875) : tot);
                    }}
                    const rate = (pop > 0) ? (count / pop * scaleFactor) : 0;
                    candidates.push({{
                        code: m.ibge_code,
                        nome: m.nome,
                        regiao: m.regiao_intermediaria,
                        pop: pop,
                        count: count,
                        rate: rate,
                        lat: m.lat,
                        lng: m.lng,
                        pci_proxima: m.pci_proxima || 'PCI SC Regional'
                    }});
                }});
            }}

            candidates.sort((a, b) => b.rate - a.rate);
            const top10 = candidates.slice(0, 10);

            // Identifica concentração regional dos 10 picos
            const regCounts = {{}};
            top10.forEach(c => {{
                regCounts[c.regiao] = (regCounts[c.regiao] || 0) + 1;
            }});
            const sortedRegs = Object.entries(regCounts).sort((a, b) => b[1] - a[1]);

            // Clusters com 2+ picos
            sortedRegs.forEach(([rname, cnt]) => {{
                if (cnt >= 2) {{
                    const rPeaks = top10.filter(p => p.regiao === rname);
                    const cLat = rPeaks.reduce((acc, p) => acc + p.lat, 0) / rPeaks.length;
                    const cLng = rPeaks.reduce((acc, p) => acc + p.lng, 0) / rPeaks.length;
                    const radius = 22000 + (cnt * 4000);
                    const circle = L.circle([cLat, cLng], {{
                        pane: 'regionsPane',
                        radius: radius,
                        color: '#f59e0b',
                        fillColor: '#f59e0b',
                        fillOpacity: 0.12,
                        weight: 1.5,
                        dashArray: '5, 5'
                    }}).bindTooltip(`<b>Concentração Espacial de Picos (${{rname}})</b><br>${{cnt}} municípios no Top 10:<br>• ${{rPeaks.map(p => p.nome).join('<br>• ')}}`, {{ sticky: true, offset: L.point(15, -15), className: 'custom-sc-tooltip' }});
                    peaksConcentrationLayerGroup.addLayer(circle);
                }}
            }});

            // Atualiza elementos visuais do card de picos se existirem
            const badgeTopic = document.getElementById('peaks-badge-topic');
            const concText = document.getElementById('peaks-concentration-text');
            const listContainer = document.getElementById('peaks-items-list');

            if (badgeTopic) badgeTopic.innerHTML = `${{topicLabel}}`;
            if (concText) {{
                concText.innerHTML = (sortedRegs.length > 0 && sortedRegs[0][1] >= 2)
                    ? `Foco em <strong>${{sortedRegs[0][0]}}</strong> (${{sortedRegs[0][1]}} municípios entre os 10 maiores picos estaduais).`
                    : 'Distribuição uniforme pelo território catarinense.';
            }}
            if (listContainer) listContainer.innerHTML = '';

            // 2. Renderiza marcadores Leaflet
            top10.forEach((item, idx) => {{
                const rank = idx + 1;
                const isTop3 = rank <= 3;
                const pulseColor = isTop3 ? 'rgba(239, 68, 68, 0.55)' : 'rgba(245, 158, 11, 0.45)';
                const badgeBg = isTop3 ? 'linear-gradient(135deg, #ef4444, #b91c1c)' : 'linear-gradient(135deg, #f59e0b, #d97706)';
                const rankTagBg = isTop3 ? '#991b1b' : '#0f172a';

                const customIcon = L.divIcon({{
                    className: 'custom-peak-divicon',
                    html: `
                        <div class="peak-marker-wrapper">
                            ${{isTop3 ? `<div class="peak-pulse-glow" style="background: ${{pulseColor}}; pointer-events: none !important;"></div>` : ''}}
                            <div class="peak-badge-icon" style="background: ${{badgeBg}};">
                                
                            </div>
                            <div class="peak-rank-tag" style="background: ${{rankTagBg}}; color: #ffffff;">
                                #${{rank}}
                            </div>
                        </div>
                    `,
                    iconSize: [42, 42],
                    iconAnchor: [21, 21],
                    popupAnchor: [0, -24]
                }});

                const marker = L.marker([item.lat, item.lng], {{
                    pane: 'peaksPane',
                    icon: customIcon,
                    riseOnHover: true
                }});

                // Tooltip posicionado acima do marcador (não sobrepõe o ícone)
                const tooltipHtml = `
                    <div style="font-size: 12px; line-height: 1.4; padding: 2px;">
                        <div style="font-weight: 800; color: #f59e0b; font-size: 13px;">#${{rank}} PICO ESTADUAL: ${{item.nome}}</div>
                        <div style="color: #94a3b8; font-size: 11px; margin-bottom: 4px;">Região de ${{item.regiao}}</div>
                        <div style="color: #fbbf24; font-weight: 800; font-size: 13px;">${{decFmt.format(item.rate)}} a cada ${{scaleLabel}}</div>
                        <div><strong>População (Censo 2022):</strong> ${{numFmt.format(item.pop)}} hab.</div>
                        <div><strong>Ocorrências (${{metricLabel}}):</strong> ${{numFmt.format(item.count)}} registros</div>
                        <div style="color: #38bdf8; margin-top: 3px; font-size: 11px;"><strong>PCI Mais Próxima:</strong> ${{item.pci_proxima}}</div>
                    </div>
                `;
                marker.bindTooltip(tooltipHtml, {{
                    sticky: false,
                    direction: 'top',
                    offset: L.point(0, -28),
                    opacity: 0.98,
                    className: 'custom-sc-tooltip'
                }});

                // Popup detalhado
                const popupHtml = `
                    <div style="font-family: 'Segoe UI', system-ui, sans-serif; width: 320px; color: #1e293b; line-height: 1.4;">
                        <div style="background: ${{badgeBg}}; color: white; padding: 12px 14px; border-radius: 10px 10px 0 0;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <span style="background: rgba(0,0,0,0.3); padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 800;">PICO #${{rank}} EM SC</span>
                                <span style="font-size: 11px; font-weight: 700;">${{topicLabel}}</span>
                            </div>
                            <div style="font-size: 17px; font-weight: 800; margin-top: 4px;">${{item.nome}}</div>
                            <div style="font-size: 11px; opacity: 0.9;">Região Intermediária de ${{item.regiao}}</div>
                        </div>
                        <div style="padding: 12px 14px; background: #ffffff; border-radius: 0 0 10px 10px; border: 1px solid #e2e8f0; border-top: none;">
                            <div style="background: #fef3c7; border: 1px solid #fde68a; border-radius: 8px; padding: 8px; text-align: center; margin-bottom: 10px;">
                                <div style="font-size: 9px; font-weight: 700; color: #92400e; text-transform: uppercase;">Taxa Proporcional Calculada</div>
                                <div style="font-size: 22px; font-weight: 900; color: #b45309; margin: 2px 0;">${{decFmt.format(item.rate)}}</div>
                                <div style="font-size: 11px; font-weight: 700; color: #78350f;">a cada ${{scaleLabel}}</div>
                            </div>

                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 8px;">
                                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 8px;">
                                    <div style="font-size: 9px; color: #64748b; font-weight: 600;">Ocorrências (${{metricLabel}})</div>
                                    <div style="font-size: 12px; font-weight: 800; color: #0f172a;">${{numFmt.format(item.count)}}</div>
                                </div>
                                <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 8px;">
                                    <div style="font-size: 9px; color: #64748b; font-weight: 600;">População (Censo 2022)</div>
                                    <div style="font-size: 12px; font-weight: 800; color: #059669;">${{numFmt.format(item.pop)}}</div>
                                </div>
                            </div>

                            <hr style="border: 0; border-top: 1px solid #f1f5f9; margin: 6px 0;">
                            <div style="font-size: 10px; color: #334155;">
                                <strong>PCI Mais Próxima:</strong> ${{item.pci_proxima}}
                            </div>
                        </div>
                    </div>
                `;
                marker.bindPopup(popupHtml, {{ maxWidth: 340 }});

                peaksLayerGroup.addLayer(marker);
                peakMarkersLookup[item.code] = marker;

                if (listContainer) {{
                    const row = document.createElement('div');
                    row.className = 'peak-list-row';
                    row.onclick = () => flyToPeak(item.code, item.lat, item.lng);
                    row.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="background: ${{rankTagBg}}; color: white; font-size: 10px; font-weight: 800; padding: 2px 6px; border-radius: 6px;">#${{rank}}</span>
                            <div>
                                <div style="font-weight: 700; color: #f8fafc; font-size: 11px;">${{item.nome}}</div>
                                <div style="font-size: 9px; color: #94a3b8;">${{item.regiao}}</div>
                            </div>
                        </div>
                        <div style="text-align: right;">
                            <div style="color: #fbbf24; font-weight: 800; font-size: 11px;">${{decFmt.format(item.rate)}}</div>
                            <div style="font-size: 8px; color: #94a3b8;">/ ${{scaleLabel}}</div>
                        </div>
                    `;
                    listContainer.appendChild(row);
                }}
            }});
        }}

        function updateDashboardView(overrideConfig) {{
            const D = window.SC_DASHBOARD_DATA;
            if (!D) return;

            const cfg = overrideConfig || window.ACTIVE_STREAMLIT_CONFIG || {{}};
            const selectTopicEl = document.getElementById('select-topic');

            const topicKey = cfg.topic || (selectTopicEl ? selectTopicEl.value : 'total');
            const metricType = cfg.metricType || 'penal';
            const scaleFactor = Number(cfg.scale) || 10000;
            const regionFilter = cfg.region || 'all';
            const yearFilter = cfg.year || 'all';

            if (cfg.showClusters !== undefined) toggleMapClusters(cfg.showClusters);
            if (cfg.showPeaks !== undefined) toggleMapPeaks(cfg.showPeaks);
            if (cfg.showPCI !== undefined) togglePCILayer(cfg.showPCI);
            if (cfg.showRoads !== undefined) toggleRoadsLayer(cfg.showRoads);

            const topicLabels = {{
                'total': 'Visão Consolidada (Todos os Casos)',
                'crianca': 'Crianças e Adolescentes (ECA)',
                'mulher': 'Mulheres em Violência de Gênero',
                'idoso': 'Pessoas Idosas (Estatuto da Pessoa Idosa)',
                'pcd': 'Pessoas com Deficiência (PCD)',
                'lgbt': 'População LGBTQIA+',
                'preso': 'Sistema Prisional e População de Rua'
            }};
            const metricNames = {{
                'penal': 'Indício Penal',
                'social': 'Demanda Socioassistencial',
                'total': 'Total Geral'
            }};

            const topicLabel = topicLabels[topicKey] || (D.topics_map && D.topics_map[topicKey]) || 'Total Geral';
            const metricLabel = metricNames[metricType] || 'Indício Penal';
            const scaleLabel = (scaleFactor === 100000) ? '100k hab' : ((scaleFactor === 50000) ? '50k hab' : '10k hab');

            // 1. Extrai valores para recalibração da escala de cores dos municípios
            const munValues = [];
            const munList = [];

            if (D.geojson_mun && D.geojson_mun.features) {{
                D.geojson_mun.features.forEach(f => {{
                    const m = (f.properties && f.properties.data) ? f.properties.data : {{}};
                    const pop = m.populacao || 10000;
                    const tDetail = (m.topics_detail && m.topics_detail[topicKey]) ? m.topics_detail[topicKey] : null;
                    let count = 0;
                    if (tDetail) {{
                        count = (tDetail[metricType] !== undefined) ? tDetail[metricType] : tDetail.total;
                    }} else if (m.topics && m.topics[topicKey] !== undefined) {{
                        const tot = m.topics[topicKey];
                        count = (metricType === 'penal') ? Math.round(tot * 0.6125) : ((metricType === 'social') ? Math.round(tot * 0.3875) : tot);
                    }}
                    const rate = (pop > 0) ? (count / pop * scaleFactor) : 0;
                    const inRegion = (regionFilter === 'all' || m.regiao_intermediaria === regionFilter);
                    if (inRegion) {{
                        munValues.push(rate);
                    }}
                    munList.push({{
                        code: m.ibge_code,
                        nome: m.nome,
                        regiao: m.regiao_intermediaria,
                        populacao: pop,
                        count: count,
                        rate: rate,
                        inRegion: inRegion
                    }});
                }});
            }}

            const minVal = munValues.length > 0 ? Math.min(...munValues) : 0;
            const maxVal = munValues.length > 0 ? Math.max(...munValues) : 100;

            // Atualiza Legenda Dinâmica
            const legTitle = document.getElementById('legend-title');
            const legMin = document.getElementById('legend-min');
            const legMid = document.getElementById('legend-mid');
            const legMax = document.getElementById('legend-max');

            if (legTitle) legTitle.textContent = `${{topicLabel}} (${{metricLabel}} / ${{scaleLabel}})`;
            if (legMin) legMin.textContent = decFmt.format(minVal);
            if (legMid) legMid.textContent = decFmt.format((minVal + maxVal) / 2);
            if (legMax) legMax.textContent = decFmt.format(maxVal);

            // 2. Atualiza Camada dos Municípios
            if (munLayerGroup) {{
                munLayerGroup.eachLayer(layer => {{
                    const m = (layer.feature && layer.feature.properties && layer.feature.properties.data) ? layer.feature.properties.data : {{}};
                    const pop = m.populacao || 10000;
                    const tDetail = (m.topics_detail && m.topics_detail[topicKey]) ? m.topics_detail[topicKey] : null;
                    let count = 0;
                    if (tDetail) {{
                        count = (tDetail[metricType] !== undefined) ? tDetail[metricType] : tDetail.total;
                    }} else if (m.topics && m.topics[topicKey] !== undefined) {{
                        const tot = m.topics[topicKey];
                        count = (metricType === 'penal') ? Math.round(tot * 0.6125) : ((metricType === 'social') ? Math.round(tot * 0.3875) : tot);
                    }}
                    const rate = (pop > 0) ? (count / pop * scaleFactor) : 0;
                    const inRegion = (regionFilter === 'all' || m.regiao_intermediaria === regionFilter);

                    const color = inRegion ? getColorGradient(rate, minVal, maxVal) : '#334155';
                    const fillOpacity = inRegion ? 0.55 : 0.10;
                    const weight = inRegion ? 0.8 : 0.3;

                    const dynStyle = {{
                        fillColor: color,
                        fillOpacity: fillOpacity,
                        color: inRegion ? '#0f172a' : '#1e293b',
                        weight: weight
                    }};
                    layer._currentDynamicStyle = dynStyle;
                    layer.setStyle(dynStyle);

                    const tooltipHtml = `
                        <div style="font-size: 12px; line-height: 1.4; padding: 2px;">
                            <div style="font-weight: 800; color: #38bdf8; font-size: 13px;">${{m.nome || 'Município'}}</div>
                            <div style="color: #94a3b8; font-size: 11px; margin-bottom: 4px;">Região de ${{m.regiao_intermediaria || 'SC'}}</div>
                            <div><strong>População (Censo 2022):</strong> ${{numFmt.format(pop)}} hab.</div>
                            <div><strong>${{topicLabel}} (${{metricLabel}}):</strong> ${{numFmt.format(count)}} ocorrências</div>
                            <div style="color: #fbbf24; font-weight: 800; margin-top: 3px; font-size: 12px;"><strong>Taxa Proporcional:</strong> ${{decFmt.format(rate)}} a cada ${{scaleLabel}}</div>
                            <div style="color: #38bdf8; font-size: 11px; margin-top: 4px;"><strong>PCI Mais Próxima:</strong> ${{m.pci_proxima || 'PCI SC Regional'}}</div>
                        </div>
                    `;

                    if (layer.getTooltip()) {{
                        layer.setTooltipContent(tooltipHtml);
                    }} else {{
                        layer.bindTooltip(tooltipHtml, {{ sticky: true, offset: L.point(15, -15), opacity: 0.98, className: 'custom-sc-tooltip' }});
                    }}
                }});
            }}

            // 3. Atualiza os Marcadores de Pico Reativos
            renderPeakMarkers(topicKey, metricType, scaleFactor, regionFilter, yearFilter);

            // 4. Se filtrado por região, enquadra a câmera do mapa na região
            if (regionFilter !== 'all' && regLayerGroup && leafletMapInstance) {{
                regLayerGroup.eachLayer(layer => {{
                    const r = (layer.feature && layer.feature.properties && layer.feature.properties.data) ? layer.feature.properties.data : {{}};
                    if (r.nome === regionFilter) {{
                        leafletMapInstance.fitBounds(layer.getBounds(), {{ padding: [25, 25], maxZoom: 10 }});
                    }}
                }});
            }}
        }}

        // Expõe globalmente para comunicação externa (Streamlit / wrapper)
        window.applyActiveFilters = function(config) {{
            updateDashboardView(config);
        }};

        function findLeafletMap() {{
            const varName = window.FOLIUM_MAP_VAR_NAME;
            if (varName && window[varName] && typeof window[varName].addLayer === 'function') {{
                return window[varName];
            }}
            for (let k in window) {{
                if (k.startsWith('map_') && window[k] && typeof window[k].addLayer === 'function') {{
                    return window[k];
                }}
            }}
            return null;
        }}

        function initDashboard() {{
            leafletMapInstance = findLeafletMap();
            if (!leafletMapInstance) {{
                setTimeout(initDashboard, 50);
                return;
            }}

            const D = window.SC_DASHBOARD_DATA;
            if (!D) return;

            if (munLayerGroup) return;

            // Panes
            leafletMapInstance.createPane('regionsPane');
            const rPane = leafletMapInstance.getPane('regionsPane');
            rPane.style.zIndex = 400;
            rPane.style.pointerEvents = 'none';

            leafletMapInstance.createPane('municipalitiesPane');
            const mPane = leafletMapInstance.getPane('municipalitiesPane');
            mPane.style.zIndex = 450;
            mPane.style.pointerEvents = 'none';

            leafletMapInstance.createPane('roadsPane');
            const rdPane = leafletMapInstance.getPane('roadsPane');
            rdPane.style.zIndex = 500;
            rdPane.style.pointerEvents = 'none';

            leafletMapInstance.createPane('pciPane');
            const pPane = leafletMapInstance.getPane('pciPane');
            pPane.style.zIndex = 600;
            pPane.style.pointerEvents = 'none';

            leafletMapInstance.createPane('peaksPane');
            const pkPane = leafletMapInstance.getPane('peaksPane');
            pkPane.style.zIndex = 700;
            pkPane.style.pointerEvents = 'none';

            if (leafletMapInstance.getPane('tooltipPane')) {{
                leafletMapInstance.getPane('tooltipPane').style.zIndex = '10000';
                leafletMapInstance.getPane('tooltipPane').style.pointerEvents = 'none';
            }}
            if (leafletMapInstance.getPane('popupPane')) {{
                leafletMapInstance.getPane('popupPane').style.zIndex = '10050';
            }}

            // 1. Camada das Regiões Intermediárias
            regLayerGroup = L.geoJSON(D.geojson_inter, {{
                pane: 'regionsPane',
                style: {{
                    fillColor: '#2dd4bf',
                    fillOpacity: 0.45,
                    color: '#0284c7',
                    weight: 2.0
                }},
                onEachFeature: function(feature, layer) {{
                    layer.bindTooltip('', {{ sticky: true, opacity: 0.98, className: 'custom-sc-tooltip' }});
                    layer.on({{
                        mouseover: function(e) {{
                            if (currentGeoLevel === 'reg') {{
                                e.target.setStyle({{
                                    weight: 3.5,
                                    color: '#ffffff',
                                    fillOpacity: 0.65
                                }});
                                if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {{
                                    e.target.bringToFront();
                                }}
                            }}
                        }},
                        mouseout: function(e) {{
                            regLayerGroup.resetStyle(e.target);
                        }}
                    }});
                }}
            }});

            // 2. Camada dos Municípios
            munLayerGroup = L.geoJSON(D.geojson_mun, {{
                pane: 'municipalitiesPane',
                style: {{
                    fillColor: '#60a5fa',
                    fillOpacity: 0.45,
                    color: '#0f172a',
                    weight: 0.7
                }},
                onEachFeature: function(feature, layer) {{
                    layer.bindTooltip('', {{ sticky: true, offset: L.point(15, -15), opacity: 0.98, className: 'custom-sc-tooltip' }});
                    layer.on({{
                        mouseover: function(e) {{
                            const l = e.target;
                            l.setStyle({{
                                weight: 2.5,
                                color: '#ffffff',
                                fillOpacity: 0.75
                            }});
                            if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {{
                                l.bringToFront();
                            }}
                        }},
                        mouseout: function(e) {{
                            if (e.target._currentDynamicStyle) {{
                                e.target.setStyle(e.target._currentDynamicStyle);
                            }} else {{
                                munLayerGroup.resetStyle(e.target);
                            }}
                        }}
                    }});
                }}
            }}).addTo(leafletMapInstance);

            // 3. Camada das Rodovias
            roadsLayerGroup = L.layerGroup();
            if (D.roads) {{
                D.roads.forEach(r => {{
                    const poly = L.polyline(r.coords, {{
                        pane: 'roadsPane',
                        color: r.color,
                        weight: r.weight,
                        opacity: 0.85
                    }}).bindTooltip(`<b>${{r.nome}}</b> (${{r.tipo === 'federal' ? 'Rodovia Federal' : 'Rodovia Estadual'}})`, {{ sticky: true, className: 'custom-sc-tooltip' }});
                    roadsLayerGroup.addLayer(poly);
                }});
            }}
            roadsLayerGroup.addTo(leafletMapInstance);

            // 4. Camada da Polícia Científica
            pciLayerGroup = L.layerGroup();
            const pciListEl = document.getElementById('pci-units-list');
            if (pciListEl) pciListEl.innerHTML = '';

            if (D.pci_units) {{
                D.pci_units.forEach(u => {{
                    const isSR = (u.nome_unidade && u.nome_unidade.includes('Superintendência')) || (u.vinculacao && u.vinculacao.includes('Sede'));
                    const markerColor = isSR ? '#ef4444' : '#0284c7';

                    const iml = (u.servicos && u.servicos.medicina_legal) ? u.servicos.medicina_legal : {{}};
                    const crim = (u.servicos && u.servicos.criminalistica) ? u.servicos.criminalistica : {{}};
                    const ident = (u.servicos && u.servicos.identificacao) ? u.servicos.identificacao : {{}};

                    const popHtml = `
                        <div style="font-family: 'Segoe UI', system-ui, sans-serif; width: 340px; color: #1e293b; line-height: 1.4;">
                            <div style="background: linear-gradient(135deg, #0284c7, #0369a1); color: white; padding: 12px 14px; border-radius: 10px 10px 0 0;">
                                <div style="font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Polícia Científica de Santa Catarina</div>
                                <div style="font-size: 14px; font-weight: 800; margin-top: 2px;">${{u.nome_unidade}}</div>
                                <div style="font-size: 11px; opacity: 0.95;">${{u.vinculacao}}</div>
                            </div>
                            <div style="padding: 12px 14px; background: #ffffff; border-radius: 0 0 10px 10px; border: 1px solid #e2e8f0; border-top: none;">
                                <div style="margin-bottom: 8px; font-size: 11px; color: #475569;">
                                    <strong>Responsável:</strong> ${{u.responsavel}}<br>
                                    <strong>E-mail:</strong> <a href="mailto:${{u.email}}" style="color: #0284c7;">${{u.email}}</a><br>
                                    <strong>Acesso Principal:</strong> <span style="background: #e0f2fe; color: #0369a1; padding: 2px 6px; border-radius: 4px; font-weight: 700;">${{u.rodovia_principal}}</span>
                                </div>
                                <hr style="border: 0; border-top: 1px solid #f1f5f9; margin: 6px 0;">
                                <div style="font-size: 11px;">
                                    <div style="margin-bottom: 6px;">
                                        <span style="background: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 10px;">MEDICINA LEGAL (IML)</span>
                                        <div style="color: #334155; margin-top: 2px;">${{iml.endereco || 'Atendimento Regional'}} | ${{iml.telefone || '(48) 3665-8000'}} | ${{iml.horario || 'Plantão 24h'}}</div>
                                    </div>
                                    <div style="margin-bottom: 6px;">
                                        <span style="background: #e0e7ff; color: #3730a3; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 10px;">CRIMINALÍSTICA & PERÍCIAS</span>
                                        <div style="color: #334155; margin-top: 2px;">${{crim.endereco || 'Atendimento Regional'}} | ${{crim.telefone || '(48) 3665-8000'}} | ${{crim.horario || 'Plantão 24h'}}</div>
                                    </div>
                                    <div>
                                        <span style="background: #ecfdf5; color: #065f46; padding: 2px 6px; border-radius: 4px; font-weight: 700; font-size: 10px;">IDENTIFICAÇÃO CIVIL (CIN)</span>
                                        <div style="color: #334155; margin-top: 2px;">${{ident.endereco || 'Atendimento Regional'}} | ${{ident.telefone || '(48) 3665-8000'}} | ${{ident.horario || 'Segunda a Sexta'}}</div>
                                    </div>
                                </div>
                                <div style="margin-top: 10px; text-align: center;">
                                    <a href="${{u.url_oficial}}" target="_blank" style="display: inline-block; background: #0284c7; color: white; text-decoration: none; padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 700;">Página Oficial</a>
                                </div>
                            </div>
                        </div>
                    `;

                    const marker = L.circleMarker([u.latitude, u.longitude], {{
                        pane: 'pciPane',
                        radius: isSR ? 8.5 : 6.5,
                        fillColor: markerColor,
                        color: '#ffffff',
                        weight: 2,
                        fillOpacity: 0.95
                    }}).bindPopup(popHtml, {{ maxWidth: 380 }}).bindTooltip(`<b>${{u.nome_unidade}}</b><br>Acesso: ${{u.rodovia_principal}}`, {{ sticky: true, className: 'custom-sc-tooltip' }});

                    pciLayerGroup.addLayer(marker);

                    if (pciListEl) {{
                        pciListEl.innerHTML += `
                            <div style="padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 11px;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 700; color: #38bdf8;">${{u.municipio}}</span>
                                    <span style="font-size: 9px; color: #94a3b8; background: rgba(255,255,255,0.08); padding: 2px 5px; border-radius: 4px;">${{u.rodovia_principal}}</span>
                                </div>
                                <div style="font-size: 10px; color: #cbd5e1; margin-top: 2px;">${{u.nome_unidade}}</div>
                                <div style="font-size: 9px; color: #64748b;">${{u.vinculacao}}</div>
                            </div>
                        `;
                    }}
                }});
            }}
            pciLayerGroup.addTo(leafletMapInstance);

            // 5. Camadas dos Pontos de Pico e Concentração Regional (peaksPane: 700)
            peaksConcentrationLayerGroup = L.layerGroup().addTo(leafletMapInstance);
            peaksLayerGroup = L.layerGroup().addTo(leafletMapInstance);

            // 6. Gráfico de Evolução Anual
            const chartCanvas = document.getElementById('scYearChart');
            if (chartCanvas && D.by_year) {{
                const ctxYear = chartCanvas.getContext('2d');
                const yearsSorted = Object.keys(D.by_year).sort();
                const yearsVals = yearsSorted.map(y => D.by_year[y]);

                new Chart(ctxYear, {{
                    type: 'line',
                    data: {{
                        labels: yearsSorted,
                        datasets: [{{
                            label: 'Registros de violação',
                            data: yearsVals,
                            borderColor: '#38bdf8',
                            backgroundColor: 'rgba(56, 189, 248, 0.15)',
                            borderWidth: 2.2,
                            fill: true,
                            tension: 0.35,
                            pointRadius: 2,
                            pointHoverRadius: 5,
                            pointBackgroundColor: '#38bdf8'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{ legend: {{ display: false }} }},
                        scales: {{
                            x: {{ grid: {{ display: false }}, ticks: {{ color: '#94a3b8', font: {{ size: 9 }} }} }},
                            y: {{
                                grid: {{ color: 'rgba(255,255,255,0.05)' }},
                                ticks: {{
                                    color: '#94a3b8',
                                    font: {{ size: 9 }},
                                    callback: function(v) {{ return v >= 1000 ? (v/1000).toFixed(0) + 'k' : v; }}
                                }}
                            }}
                        }}
                    }}
                }});
            }}

            // 7. Atualização Inicial da Visão Completa
            updateDashboardView();
        }}

        // Inicialização garantida
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initDashboard);
        }} else {{
            initDashboard();
        }}
        window.addEventListener('load', initDashboard);
    </script>
    """

    m.get_root().html.add_child(folium.Element(embedded_html))
    m.save(str(output_path))
    print(f"Dashboard geral salvo com sucesso em: '{output_path}'")


def main():
    root_dir = Path(__file__).resolve().parent
    if root_dir.name == "scripts":
        root_dir = root_dir.parent

    client = IBGEClient()
    uf_alvo = "SC"

    print("======================================================================")
    print("GERADOR DO DASHBOARD DINÂMICO SC: DISQUE 100 + CENSO 2022 + PICOS / 10K HAB")
    print("======================================================================")

    # 1. População Oficial dos 295 Municípios (Censo 2022)
    pop_map = fetch_sc_population_censo_2022()

    # 2. Metadados Oficiais dos Municípios de SC via IBGE Localidades
    print("2. Obtendo metadados oficiais dos municípios de Santa Catarina...")
    df_loc_sc = client.get_municipios_df(uf=uf_alvo, engine="polars")

    # 3. Processa microdados de 2011 a 2026
    sc_data = process_disque100_sc_data(parquet_dir=root_dir, df_ibge_sc=df_loc_sc, pop_map=pop_map)

    # 4. Lê dados das 30 unidades da Polícia Científica de SC
    pci_candidates = [
        root_dir / "data" / "processed" / "unidades_policia_cientifica_sc.json",
        root_dir / "unidades_policia_cientifica_sc.json"
    ]
    pci_file = next((p for p in pci_candidates if p.exists()), None)
    if not pci_file or not pci_file.exists():
        print("Scraping das unidades da Polícia Científica...")
        os.system(f"{sys.executable} scrape_policia_cientifica_sc.py")
        pci_file = next((p for p in pci_candidates if p.exists()), None)

    with open(pci_file, "r", encoding="utf-8") as f:
        pci_units = json.load(f)

    # 5. Obtém malhas vetoriais de SC
    print("5. Obtendo malha dos 295 municípios e 7 regiões intermediárias...")
    geojson_sc = client.get_malha_municipios_uf_geojson(uf=uf_alvo, intrarregiao="municipio", qualidade="minima")
    geojson_inter = client.get_malha_municipios_uf_geojson(uf=uf_alvo, intrarregiao="regiao-intermediaria", qualidade="minima")

    # 6. Calcula Centróides e 10 Pontos de Pico por Categoria (Proporção a cada 10k hab)
    peaks_info = compute_peaks_and_centroids(sc_data, geojson_sc, pci_units)

    # 7. Constrói o Dashboard no Folium (Salva tanto em dashboards/ quanto na raiz)
    dash_dir = root_dir / "dashboards"
    dash_dir.mkdir(exist_ok=True)
    output_html_dash = dash_dir / "dashboard_sc_disque100_folium.html"

    generate_interactive_dashboard(sc_data, pci_units, geojson_sc, geojson_inter, peaks_info, output_html_dash)

    print("\n======================================================================")
    print(f"Dashboard Concluído com Sucesso!")
    print(f" . Registros de violacao em SC: {sc_data['total_sc']:,}")
    print(f" • População SC (Censo 2022): {sum(pop_map.values()):,}")
    print(f" • Categorias Analisadas: {len(TOPICS_MAP)} tipos de incidentes")
    print(f" • Pontos de Pico: 10 picos por categoria (proporção / 10k hab)")
    print(f" • Unidades da Polícia Científica: {len(pci_units)} unidades")
    print(f"Salvo em: file://{output_html_dash}")
    print("======================================================================")


if __name__ == "__main__":
    main()
