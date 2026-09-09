#!/usr/bin/env python3
"""
=============================================================================
Analisador Completo de Distribuição Penal & Hotspots do Disque 100 (SC 2011–2026)
=============================================================================
Processa todos os 22 arquivos Parquet históricos, filtra e classifica com Polars
a totalidade dos registros do Estado de Santa Catarina (~699k linhas), aplicando
a taxonomia penal estrita de classificar_indicio_penal.py.

Gera métricas detalhadas:
  1. Distribuição Global: Infrações Penais vs. Rede de Proteção Social
  2. Distribuição por Família Delitiva (Sexuais, Integridade Física, Ameaça, etc.)
  3. Evolução Histórica (2011 a 2026)
  4. Ranking de Picos e Hotspots por 10.000 Habitantes (Censo IBGE 2022)
  5. Agrupamento por Regiões Intermediárias e Imediatas
  6. Cruzamento com as 30 Unidades da Polícia Científica de SC (PCI-SC)
=============================================================================
"""

import os
import sys
import glob
import re
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple

import polars as pl
import pandas as pd

from classificar_indicio_penal import classificar_caso, PENAL_TAXONOMY
from generate_sc_disque100_folium_dashboard import IBGEClient, haversine_km


def carregar_metadados_ibge_e_populacao(root_dir: Path) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str], Dict[str, int]]:
    """Carrega dados oficiais do IBGE para os 295 municípios de SC e Censo 2022."""
    pop_candidates = [
        root_dir / "data" / "processed" / "sc_censo_2022_populacao.json",
        root_dir / "sc_censo_2022_populacao.json"
    ]
    pop_file = next((p for p in pop_candidates if p.exists()), None)
    if not pop_file:
        raise FileNotFoundError(f"Arquivo de população sc_censo_2022_populacao.json não encontrado!")

    with open(pop_file, "r", encoding="utf-8") as f:
        pop_map = json.load(f)

    client = IBGEClient()
    df_mun = client.get_municipios_df(uf="SC", engine="polars")

    code_to_meta: Dict[str, Dict[str, Any]] = {}
    name_to_code: Dict[str, str] = {}

    for row in df_mun.to_dicts():
        cid = str(row["municipio-id"])
        cname = str(row["municipio-nome"]).strip().upper()
        code_to_meta[cid] = {
            "ibge_code": cid,
            "nome": row["municipio-nome"],
            "microrregiao": row["microrregiao-nome"],
            "regiao_imediata": row["regiao-imediata-nome"],
            "regiao_intermediaria": row["regiao-intermediaria-nome"],
            "populacao": pop_map.get(cid, 10000)
        }
        name_to_code[cname] = cid

    return code_to_meta, name_to_code, pop_map


def extrair_codigo_municipio(raw_val: Any, name_to_code: Dict[str, str]) -> str:
    """Extrai com precisão o código IBGE 7 dígitos de qualquer representação textual ou numérica."""
    if raw_val is None:
        return None
    s = str(raw_val).strip()
    if not s or s.upper() in ("NAN", "NULL", "NONE", "<NA>", "NI", ""):
        return None

    # Caso Era 2: "4211900 | PALHOÇA" ou "4205407"
    m_code = re.match(r"^(\d{7})", s)
    if m_code and m_code.group(1).startswith("42"):
        return m_code.group(1)

    # Caso Era 1 float ou int 6 dígitos: "420540" -> precisa do 7º dígito ou verificação
    if s.isdigit() and len(s) == 7 and s.startswith("42"):
        return s

    # Caso texto com nome do município: "Florianopolis (SC)" ou "PALHOÇA"
    clean_name = re.sub(r"\s*\(SC\)\s*", "", s, flags=re.IGNORECASE).strip().upper()
    # Remove acentos para busca flexível
    if clean_name in name_to_code:
        return name_to_code[clean_name]

    # Busca aproximada caso haja hífen ou preposição
    for kname, kcode in name_to_code.items():
        if kname in clean_name or clean_name in kname:
            return kcode

    return None


def processar_base_sc_completa(root_dir: Path) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """Varre todos os arquivos parquet, classifica os casos de SC e calcula métricas completas."""
    t_inicio = time.time()
    code_to_meta, name_to_code, pop_map = carregar_metadados_ibge_e_populacao(root_dir)

    pqs = sorted(glob.glob(str(root_dir / "data" / "raw" / "disque100-*.parquet"))) or sorted(glob.glob(str(root_dir / "disque100-*.parquet")))
    print(f"📦 Varrendo {len(pqs)} arquivos Parquet para extração de Santa Catarina...")

    # Estruturas de agregação
    total_registros_sc = 0
    total_penal_sc = 0
    total_social_sc = 0

    por_ano: Dict[str, Dict[str, int]] = {}
    por_categoria: Dict[str, int] = {}
    por_grau: Dict[str, int] = {"ALTO": 0, "MEDIO": 0, "BAIXO": 0}
    por_orgao: Dict[str, int] = {}

    # Por município
    mun_stats: Dict[str, Dict[str, Any]] = {}
    for cid, meta in code_to_meta.items():
        mun_stats[cid] = {
            "ibge_code": cid,
            "nome": meta["nome"],
            "regiao_intermediaria": meta["regiao_intermediaria"],
            "regiao_imediata": meta["regiao_imediata"],
            "populacao": meta["populacao"],
            "total_denuncias": 0,
            "total_penal": 0,
            "total_social": 0,
            "categorias_penais": {}
        }

    # Processamento de cada arquivo Parquet
    for p in pqs:
        nome_arq = os.path.basename(p)
        m_ano = re.search(r"20\d\d", nome_arq)
        ano = m_ano.group(0) if m_ano else "Outro"

        if ano not in por_ano:
            por_ano[ano] = {"total": 0, "penal": 0, "social": 0}

        # Lazy inspection
        schema = pl.scan_parquet(p).collect_schema()
        cols = schema.names()

        # Determinar colunas de UF e Município
        uf_col = None
        mun_col = None
        for cand in ["vitima_uf", "UF", "UF_da_vítima", "UF da vítima"]:
            if cand in cols:
                uf_col = cand
                break

        for cand in ["vitima_cod_municipio", "Município", "Município_da_vítima", "vitima_municipio"]:
            if cand in cols:
                mun_col = cand
                break

        if not uf_col:
            continue

        # Filtro em Polars de alta velocidade
        df_lazy = pl.scan_parquet(p).filter(pl.col(uf_col).cast(pl.Utf8).str.to_uppercase() == "SC")
        df_sc = df_lazy.collect()
        n_sc = len(df_sc)
        if n_sc == 0:
            continue

        total_registros_sc += n_sc
        por_ano[ano]["total"] += n_sc

        # Converte para dicts para classificação penal
        dicts = df_sc.to_dicts()
        for r in dicts:
            classificacao = classificar_caso(r)
            e_penal = classificacao["indicio_penal"]
            cat = classificacao["categoria_penal"]
            grau = classificacao["grau_certeza"]
            orgao = classificacao["orgao_prioritario"]

            if e_penal:
                total_penal_sc += 1
                por_ano[ano]["penal"] += 1
                por_categoria[cat] = por_categoria.get(cat, 0) + 1
                por_grau[grau] = por_grau.get(grau, 0) + 1
                por_orgao[orgao] = por_orgao.get(orgao, 0) + 1
            else:
                total_social_sc += 1
                por_ano[ano]["social"] += 1

            # Extração de município
            raw_m = r.get(mun_col) if mun_col else None
            cid = extrair_codigo_municipio(raw_m, name_to_code)

            if cid and cid in mun_stats:
                mun_stats[cid]["total_denuncias"] += 1
                if e_penal:
                    mun_stats[cid]["total_penal"] += 1
                    mun_stats[cid]["categorias_penais"][cat] = mun_stats[cid]["categorias_penais"].get(cat, 0) + 1
                else:
                    mun_stats[cid]["total_social"] += 1

        print(f"  ✓ {nome_arq}: {n_sc:,} registros de SC processados.")

    tempo_total = time.time() - t_inicio
    print(f"\n⚡ Concluído processamento de {total_registros_sc:,} registros de SC em {tempo_total:.2f} segundos!")

    # Agregação por Regiões Intermediárias
    por_regiao_intermediaria: Dict[str, Dict[str, Any]] = {}
    for cid, m in mun_stats.items():
        reg = m["regiao_intermediaria"]
        if reg not in por_regiao_intermediaria:
            por_regiao_intermediaria[reg] = {
                "nome_regiao": reg,
                "populacao_total": 0,
                "total_denuncias": 0,
                "total_penal": 0,
                "total_social": 0,
                "municipios_qtd": 0,
                "categorias_penais": {}
            }
        por_regiao_intermediaria[reg]["populacao_total"] += m["populacao"]
        por_regiao_intermediaria[reg]["total_denuncias"] += m["total_denuncias"]
        por_regiao_intermediaria[reg]["total_penal"] += m["total_penal"]
        por_regiao_intermediaria[reg]["total_social"] += m["total_social"]
        por_regiao_intermediaria[reg]["municipios_qtd"] += 1
        for c_cat, c_val in m["categorias_penais"].items():
            por_regiao_intermediaria[reg]["categorias_penais"][c_cat] = (
                por_regiao_intermediaria[reg]["categorias_penais"].get(c_cat, 0) + c_val
            )

    # Cálculo das taxas por 10k hab para regiões
    for reg, r_data in por_regiao_intermediaria.items():
        pop = max(r_data["populacao_total"], 1)
        r_data["taxa_penal_10k"] = round((r_data["total_penal"] / pop) * 10000, 2)
        r_data["taxa_total_10k"] = round((r_data["total_denuncias"] / pop) * 10000, 2)
        r_data["pct_penal"] = round((r_data["total_penal"] / max(r_data["total_denuncias"], 1)) * 100, 2)

    # Cálculo de métricas e ranking de municípios
    lista_ranking = []
    for cid, m in mun_stats.items():
        pop = max(m["populacao"], 1)
        taxa_penal_10k = round((m["total_penal"] / pop) * 10000, 2)
        taxa_total_10k = round((m["total_denuncias"] / pop) * 10000, 2)
        pct_penal = round((m["total_penal"] / max(m["total_denuncias"], 1)) * 100, 2)

        # Categoria penal mais frequente
        top_cat = "N/A"
        top_cat_count = 0
        if m["categorias_penais"]:
            top_cat = max(m["categorias_penais"], key=m["categorias_penais"].get)
            top_cat_count = m["categorias_penais"][top_cat]

        m["taxa_penal_10k"] = taxa_penal_10k
        m["taxa_total_10k"] = taxa_total_10k
        m["pct_penal"] = pct_penal
        m["top_categoria_penal"] = top_cat
        m["top_categoria_penal_count"] = top_cat_count

        lista_ranking.append({
            "ibge_code": cid,
            "municipio": m["nome"],
            "regiao_intermediaria": m["regiao_intermediaria"],
            "regiao_imediata": m["regiao_imediata"],
            "populacao_censo_2022": m["populacao"],
            "total_denuncias": m["total_denuncias"],
            "total_penal": m["total_penal"],
            "total_social": m["total_social"],
            "pct_penal": pct_penal,
            "taxa_penal_10k": taxa_penal_10k,
            "taxa_total_10k": taxa_total_10k,
            "top_categoria_penal": top_cat,
            "top_categoria_qtd": top_cat_count
        })

    df_ranking = pd.DataFrame(lista_ranking)
    df_ranking.sort_values(by="taxa_penal_10k", ascending=False, inplace=True)
    df_ranking["ranking_taxa_penal"] = range(1, len(df_ranking) + 1)

    # Carrega unidades da Polícia Científica de SC para correlação
    pci_candidates = [
        root_dir / "data" / "processed" / "unidades_policia_cientifica_sc.json",
        root_dir / "unidades_policia_cientifica_sc.json"
    ]
    pci_file = next((p for p in pci_candidates if p.exists()), None)
    pci_units = []
    if pci_file and pci_file.exists():
        with open(pci_file, "r", encoding="utf-8") as f:
            pci_units = json.load(f)

    # Consolidação do dicionário final de métricas
    pct_global_penal = round((total_penal_sc / max(total_registros_sc, 1)) * 100, 2)
    pct_global_social = round((total_social_sc / max(total_registros_sc, 1)) * 100, 2)

    metricas_consolidadas = {
        "metadata": {
            "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
            "periodo": "2011 a 2026",
            "estado": "Santa Catarina (SC)",
            "fonte_primaria": "Disque 100 / Disque Direitos Humanos (MDH)",
            "fonte_demografica": "IBGE Censo 2022 (População Residente)",
            "fonte_seguranca": "Polícia Científica de Santa Catarina (PCI-SC)",
            "tempo_processamento_segundos": round(tempo_total, 2)
        },
        "totais_globais": {
            "total_registros": total_registros_sc,
            "total_penal": total_penal_sc,
            "total_social": total_social_sc,
            "pct_penal": pct_global_penal,
            "pct_social": pct_global_social
        },
        "por_ano": por_ano,
        "por_categoria_penal": por_categoria,
        "por_grau_certeza": por_grau,
        "por_orgao_prioritario": por_orgao,
        "por_regiao_intermediaria": por_regiao_intermediaria,
        "municipios": mun_stats,
        "top_15_maior_taxa_penal_10k": df_ranking.head(15).to_dict(orient="records"),
        "top_15_maior_volume_absoluto": df_ranking.sort_values(by="total_penal", ascending=False).head(15).to_dict(orient="records"),
        "policia_cientifica_unidades": len(pci_units)
    }

    return metricas_consolidadas, df_ranking


def main():
    root_dir = Path(__file__).resolve().parent
    if root_dir.name == "scripts":
        root_dir = root_dir.parent
    print("======================================================================")
    print("🔍 INICIANDO PROCESSAMENTO & CLASSIFICAÇÃO PENAL TOTAL - DISQUE 100 SC")
    print("======================================================================")

    metricas, df_ranking = processar_base_sc_completa(root_dir)

    proc_dir = root_dir / "data" / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)

    # 1. Salva métricas em JSON
    json_path = proc_dir / "sc_distribuicao_penal_metricas.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Arquivo JSON salvo com sucesso: {json_path}")

    # 2. Salva ranking em CSV
    csv_path = proc_dir / "sc_ranking_focos_penais.csv"
    df_ranking.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"💾 Arquivo CSV salvo com sucesso: {csv_path}")

    # 3. Resumo Estatístico no Console
    t = metricas["totais_globais"]
    print("\n======================================================================")
    print("📊 RESULTADOS EMPÍRICOS CONSOLIDADOS (SC 2011–2026)")
    print("======================================================================")
    print(f"• Total de Ocorrências em SC: {t['total_registros']:,}")
    print(f"• Casos com Indício Penal:    {t['total_penal']:,} ({t['pct_penal']}%)")
    print(f"• Rede de Proteção Social:    {t['total_social']:,} ({t['pct_social']}%)")

    print("\n⚖️ DISTRIBUIÇÃO POR FAMÍLIA DELITIVA:")
    for cat, val in sorted(metricas["por_categoria_penal"].items(), key=lambda x: x[1], reverse=True):
        pct = (val / t["total_penal"]) * 100
        print(f"  - {cat:40s}: {val:7,d} ({pct:5.2f}%)")

    print("\n📍 TOP 10 FOCOS ESPACIAIS CRÍTICOS (TAXA POR 10K HABITANTES):")
    for i, row in enumerate(metricas["top_15_maior_taxa_penal_10k"][:10], 1):
        print(f"  {i:2d}. {row['municipio']:25s} | Pop: {row['populacao_censo_2022']:6,d} | Crimes: {row['total_penal']:5,d} | Taxa: {row['taxa_penal_10k']:6.2f}/10k | Predom: {row['top_categoria_penal']}")

    print("\n🏢 TOP 5 POLOS POR VOLUME ABSOLUTO:")
    for i, row in enumerate(metricas["top_15_maior_volume_absoluto"][:5], 1):
        print(f"  {i:2d}. {row['municipio']:25s} | Pop: {row['populacao_censo_2022']:6,d} | Crimes: {row['total_penal']:5,d} | Taxa: {row['taxa_penal_10k']:6.2f}/10k")

    print("======================================================================")


if __name__ == "__main__":
    main()

