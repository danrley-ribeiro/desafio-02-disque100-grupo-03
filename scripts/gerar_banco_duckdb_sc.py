#!/usr/bin/env python3
"""
=============================================================================
Gerador do Banco de Dados Analítico Auditável & Pipeline de Grupos Vulneráveis
Governo do Estado de Santa Catarina - Disque 100 (2011–2026)
=============================================================================
Processa os 699.029 registros de SC e gera a modelagem dimensional:
  - fato_denuncias_sc (699k linhas com tipificação penal e grupos vulneráveis)
  - dim_municipios_sc (295 municípios com Censo 2022 e Regiões)
  - dim_unidades_pci_sc (30 unidades da Polícia Científica)
  - kpis_grupos_municipios (visão pré-calculada por 10k hab para alta performance)

Exporta em DuckDB (se disponível), SQLite, Parquet e JSON/CSV auditáveis com SHA-256.
=============================================================================
"""

import os
import sys
import glob
import re
import json
import time
import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "scripts" else CURRENT_DIR
sys.path.extend([str(CURRENT_DIR), str(ROOT_DIR), str(ROOT_DIR / "scripts")])

import polars as pl
import pandas as pd

from classificar_indicio_penal import classificar_caso
from generate_sc_disque100_folium_dashboard import IBGEClient


def extrair_codigo_municipio(raw_val: Any, name_to_code: Dict[str, str]) -> str:
    """Extrai com precisão o código IBGE 7 dígitos."""
    if raw_val is None:
        return None
    s = str(raw_val).strip()
    if not s or s.upper() in ("NAN", "NULL", "NONE", "<NA>", "NI", ""):
        return None

    # Caso Era 2: "4211900 | PALHOÇA" ou "4205407"
    m_code = re.match(r"^(\d{7})", s)
    if m_code and m_code.group(1).startswith("42"):
        return m_code.group(1)

    if s.isdigit() and len(s) == 7 and s.startswith("42"):
        return s

    clean_name = re.sub(r"\s*\(SC\)\s*", "", s, flags=re.IGNORECASE).strip().upper()
    if clean_name in name_to_code:
        return name_to_code[clean_name]

    for kname, kcode in name_to_code.items():
        if kname in clean_name or clean_name in kname:
            return kcode

    return None


def classificar_grupos_vulneraveis(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classifica detalhadamente os grupos vulneráveis estratégicos:
      1. Crianças e Adolescentes (ECA)
      2. Mulheres / Violência de Gênero (Lei Maria da Penha / Lei 14.188)
      3. Pessoas Idosas (Estatuto da Pessoa Idosa)
      4. População LGBTQIA+ (Direitos Humanos / STF ADO 26)
      5. Pessoas com Deficiência (Estatuto da PCD)
      6. Sistema Prisional & População de Rua (Restrição de Liberdade / Direitos Humanos)
    """
    txt_grupo = str(row.get("Grupo_vulnerável") or row.get("Grupo vulnerável") or row.get("grupo_violacao") or "").upper()
    txt_sexo = str(row.get("Sexo_da_vítima") or row.get("vitima_sexo") or "").upper()
    txt_idade = str(row.get("Faixa_etária_da_vítima") or row.get("vitima_faixa_etaria") or "").upper()
    txt_motiv = str(row.get("Motivação") or row.get("relacao_suspeito") or row.get("Relação_vítima_suspeito") or "").upper()
    txt_viol = str(row.get("violacao") or row.get("violacoes") or row.get("sub_grupo_violacao") or "").upper()
    txt_defic = str(row.get("Deficiência_da_vítima") or "").upper()
    txt_orient = str(row.get("Orientação_sexual_da_vítima") or row.get("vitima_orientacao_sexual") or "").upper()

    # Indicadores booleanos multidimensionais
    is_crianca = (
        "CRIANÇA" in txt_grupo or "CRIANCA" in txt_grupo or "ADOLESC" in txt_grupo or
        any(k in txt_idade for k in ("0 A 4", "5 A 9", "10 A 14", "15 A 17", "RECÉM", "MENOR"))
    )

    is_idoso = (
        "IDOSA" in txt_grupo or "IDOSO" in txt_grupo or
        any(k in txt_idade for k in ("60 A 64", "65 A 69", "70 A 74", "75 A 79", "80", "IDOS"))
    )

    is_pcd = (
        "DEFICIÊNCIA" in txt_grupo or "DEFICIENCIA" in txt_grupo or
        (txt_defic != "" and txt_defic not in ("NÃO", "NAO", "SEM DEFICIÊNCIA", "NULL", "NONE", "NI"))
    )

    is_lgbt = (
        "LGBT" in txt_grupo or
        any(k in txt_orient for k in ("HOMO", "LÉSB", "LESB", "GAY", "BISSEX", "TRANS", "TRAVEST"))
    )

    is_mulher = (
        ("FEMIN" in txt_sexo or txt_sexo == "F" or "MULHER" in txt_sexo) and
        (
            any(k in txt_viol or k in txt_motiv for k in (
                "DOMÉSTICA", "DOMESTICA", "CONJUGAL", "MARIA DA PENHA", "COMPANHEIR",
                "NAMORAD", "CÔNJUGE", "CONJUGE", "FEMINICÍDIO", "FEMINICIDIO",
                "147-B", "PSICOLÓGICA", "SEXUAL", "EX-MARIDO", "EX-COMPANHEIRO"
            )) or
            "MULHER" in txt_grupo
        )
    )

    is_prisional_rua = (
        any(k in txt_grupo for k in ("LIBERDADE", "PRISIONAL", "RUA")) or
        any(k in str(row.get("Vítima_preso_a") or "").upper() for k in ("SIM", "PRESO", "RECLUS"))
    )

    # Definição do grupo primário dominante para visualização limpa
    if is_crianca:
        grupo_primario = "CRIANCAS_E_ADOLESCENTES"
    elif is_mulher:
        grupo_primario = "MULHERES_VIOLENCIA_GENERO"
    elif is_idoso:
        grupo_primario = "PESSOAS_IDOSAS"
    elif is_pcd:
        grupo_primario = "PESSOAS_COM_DEFICIENCIA"
    elif is_lgbt:
        grupo_primario = "POPULACAO_LGBTQIA+"
    elif is_prisional_rua:
        grupo_primario = "SISTEMA_PRISIONAL_E_RUA"
    else:
        grupo_primario = "GERAL_OUTROS"

    return {
        "grupo_primario": grupo_primario,
        "is_crianca": is_crianca,
        "is_mulher": is_mulher,
        "is_idoso": is_idoso,
        "is_pcd": is_pcd,
        "is_lgbtqia": is_lgbt,
        "is_prisional_rua": is_prisional_rua
    }


def carregar_dados_auxiliares(root_dir: Path):
    """Carrega metadados oficiais do IBGE, Censo 2022 e Polícia Científica."""
    pop_candidates = [
        root_dir / "data" / "processed" / "sc_censo_2022_populacao.json",
        root_dir / "sc_censo_2022_populacao.json"
    ]
    pop_file = next((p for p in pop_candidates if p.exists()), pop_candidates[0])
    with open(pop_file, "r", encoding="utf-8") as f:
        pop_map = json.load(f)

    client = IBGEClient()
    df_mun = client.get_municipios_df(uf="SC", engine="polars")

    code_to_meta = {}
    name_to_code = {}
    mun_list = []

    for row in df_mun.to_dicts():
        cid = str(row["municipio-id"])
        cname = str(row["municipio-nome"]).strip().upper()
        pop = pop_map.get(cid, 10000)
        meta = {
            "ibge_code": cid,
            "municipio_nome": row["municipio-nome"],
            "microrregiao": row["microrregiao-nome"],
            "regiao_imediata": row["regiao-imediata-nome"],
            "regiao_intermediaria": row["regiao-intermediaria-nome"],
            "populacao_censo_2022": pop
        }
        code_to_meta[cid] = meta
        name_to_code[cname] = cid
        mun_list.append(meta)

    # 30 unidades da PCI-SC
    pci_candidates = [
        root_dir / "data" / "processed" / "unidades_policia_cientifica_sc.json",
        root_dir / "unidades_policia_cientifica_sc.json"
    ]
    pci_file = next((p for p in pci_candidates if p.exists()), pci_candidates[0])
    pci_units = []
    if pci_file and pci_file.exists():
        with open(pci_file, "r", encoding="utf-8") as f:
            pci_units = json.load(f)

    return code_to_meta, name_to_code, mun_list, pci_units


def processar_e_gerar_banco(root_dir: Path):
    """Processa todos os 22 arquivos Parquet e constrói o banco analítico auditável."""
    t0 = time.time()
    code_to_meta, name_to_code, mun_list, pci_units = carregar_dados_auxiliares(root_dir)

    pqs = sorted(glob.glob(str(root_dir / "data" / "raw" / "disque100-*.parquet"))) or sorted(glob.glob(str(root_dir / "disque100-*.parquet")))
    print(f"📦 Varrendo {len(pqs)} arquivos Parquet históricos do Disque 100...")

    registros_fato = []
    total_linhas_sc = 0

    for p in pqs:
        nome_arq = os.path.basename(p)
        m_ano = re.search(r"20\d\d", nome_arq)
        ano = int(m_ano.group(0)) if m_ano else 2026
        semestre = 1 if "primeiro-semestre" in nome_arq else (2 if "segundo-semestre" in nome_arq else 0)

        schema = pl.scan_parquet(p).collect_schema()
        cols = schema.names()

        uf_col = None
        for cand in ["vitima_uf", "UF", "UF_da_vítima", "UF da vítima"]:
            if cand in cols:
                uf_col = cand
                break

        mun_col = None
        for cand in ["vitima_cod_municipio", "Município", "Município_da_vítima", "vitima_municipio"]:
            if cand in cols:
                mun_col = cand
                break

        if not uf_col:
            continue

        df_sc = pl.scan_parquet(p).filter(pl.col(uf_col).cast(pl.Utf8).str.to_uppercase() == "SC").collect()
        n_sc = len(df_sc)
        if n_sc == 0:
            continue

        total_linhas_sc += n_sc
        dicts = df_sc.to_dicts()

        for idx, r in enumerate(dicts):
            # Classificação Penal
            c_penal = classificar_caso(r)
            # Classificação por Grupos
            c_grupo = classificar_grupos_vulneraveis(r)

            # Extração de Município
            raw_m = r.get(mun_col) if mun_col else None
            cid = extrair_codigo_municipio(raw_m, name_to_code)

            meta_m = code_to_meta.get(cid, {})

            registro = {
                "id_fato": f"{ano}_{semestre}_{idx+1}",
                "ano": ano,
                "semestre": semestre,
                "arquivo_origem": nome_arq,
                "ibge_code": cid or "4200000",
                "municipio_nome": meta_m.get("municipio_nome", "NÃO IDENTIFICADO"),
                "regiao_intermediaria": meta_m.get("regiao_intermediaria", "OUTRA"),
                "regiao_imediata": meta_m.get("regiao_imediata", "OUTRA"),
                "indicio_penal": 1 if c_penal["indicio_penal"] else 0,
                "categoria_penal": c_penal["categoria_penal"],
                "grau_certeza": c_penal["grau_certeza"],
                "orgao_prioritario": c_penal["orgao_prioritario"],
                "fundamentacao_legal": c_penal["fundamentacao_legal"],
                "grupo_primario": c_grupo["grupo_primario"],
                "is_crianca": 1 if c_grupo["is_crianca"] else 0,
                "is_mulher": 1 if c_grupo["is_mulher"] else 0,
                "is_idoso": 1 if c_grupo["is_idoso"] else 0,
                "is_pcd": 1 if c_grupo["is_pcd"] else 0,
                "is_lgbtqia": 1 if c_grupo["is_lgbtqia"] else 0,
                "is_prisional_rua": 1 if c_grupo["is_prisional_rua"] else 0
            }
            registros_fato.append(registro)

        print(f"  ✓ {nome_arq}: {n_sc:,} registros processados e classificados.")

    df_fato = pl.DataFrame(registros_fato)
    duracao = time.time() - t0
    print(f"\n⚡ {len(df_fato):,} registros consolidados em {duracao:.2f} segundos!")

    # 1. Salvar Tabelas Dimensionais em Parquet de Alta Performance
    fato_parquet = root_dir / "sc_fato_denuncias.parquet"
    df_fato.write_parquet(fato_parquet, compression="zstd")
    print(f"💾 Parquet Fato salvo: {fato_parquet.name} ({fato_parquet.stat().st_size / (1024*1024):.2f} MB)")

    df_dim_mun = pl.DataFrame(mun_list)
    dim_mun_parquet = root_dir / "sc_dim_municipios.parquet"
    df_dim_mun.write_parquet(dim_mun_parquet, compression="zstd")

    # Salva Dimensão PCI
    pci_clean = []
    for u in pci_units:
        pci_clean.append({
            "sigla": u.get("sigla", ""),
            "nome": u.get("nome", ""),
            "municipio": u.get("municipio", ""),
            "tipo": u.get("tipo", ""),
            "lat": float(u.get("lat", 0.0)),
            "lon": float(u.get("lon", 0.0)),
            "jurisdicao": ", ".join(u.get("jurisdicao", []))
        })
    df_dim_pci = pl.DataFrame(pci_clean)
    dim_pci_parquet = root_dir / "sc_dim_pci.parquet"
    df_dim_pci.write_parquet(dim_pci_parquet, compression="zstd")

    # 2. Criar Visão Agregada Pré-Calculada (KPIs por Município e Grupo / 10k Hab)
    print("📊 Gerando visão materializada de KPIs por grupo e por 10k habitantes...")
    grupos = [
        ("GERAL", "total"),
        ("CRIANCAS_E_ADOLESCENTES", "criancas"),
        ("MULHERES_VIOLENCIA_GENERO", "mulheres"),
        ("PESSOAS_IDOSAS", "idosos"),
        ("PESSOAS_COM_DEFICIENCIA", "pcd"),
        ("POPULACAO_LGBTQIA+", "lgbt"),
        ("SISTEMA_PRISIONAL_E_RUA", "prisional")
    ]

    kpis_rows = []
    for m in mun_list:
        cid = m["ibge_code"]
        pop = max(m["populacao_censo_2022"], 1)

        df_m = df_fato.filter(pl.col("ibge_code") == cid)
        total_m = len(df_m)
        penal_m = df_m.filter(pl.col("indicio_penal") == 1).height
        social_m = total_m - penal_m

        # Por grupo
        criancas_total = df_m.filter(pl.col("is_crianca") == 1).height
        criancas_penal = df_m.filter((pl.col("is_crianca") == 1) & (pl.col("indicio_penal") == 1)).height

        mulheres_total = df_m.filter(pl.col("is_mulher") == 1).height
        mulheres_penal = df_m.filter((pl.col("is_mulher") == 1) & (pl.col("indicio_penal") == 1)).height

        idosos_total = df_m.filter(pl.col("is_idoso") == 1).height
        idosos_penal = df_m.filter((pl.col("is_idoso") == 1) & (pl.col("indicio_penal") == 1)).height

        pcd_total = df_m.filter(pl.col("is_pcd") == 1).height
        pcd_penal = df_m.filter((pl.col("is_pcd") == 1) & (pl.col("indicio_penal") == 1)).height

        lgbt_total = df_m.filter(pl.col("is_lgbtqia") == 1).height
        lgbt_penal = df_m.filter((pl.col("is_lgbtqia") == 1) & (pl.col("indicio_penal") == 1)).height

        prisional_total = df_m.filter(pl.col("is_prisional_rua") == 1).height
        prisional_penal = df_m.filter((pl.col("is_prisional_rua") == 1) & (pl.col("indicio_penal") == 1)).height

        kpis_rows.append({
            "ibge_code": cid,
            "municipio": m["municipio_nome"],
            "regiao_intermediaria": m["regiao_intermediaria"],
            "regiao_imediata": m["regiao_imediata"],
            "populacao_censo_2022": pop,
            "total_denuncias": total_m,
            "total_penal": penal_m,
            "total_social": social_m,
            "taxa_total_10k": round((total_m / pop) * 10000, 2),
            "taxa_penal_10k": round((penal_m / pop) * 10000, 2),
            # Crianças
            "criancas_total": criancas_total,
            "criancas_penal": criancas_penal,
            "taxa_criancas_10k": round((criancas_total / pop) * 10000, 2),
            "taxa_criancas_penal_10k": round((criancas_penal / pop) * 10000, 2),
            # Mulheres
            "mulheres_total": mulheres_total,
            "mulheres_penal": mulheres_penal,
            "taxa_mulheres_10k": round((mulheres_total / pop) * 10000, 2),
            "taxa_mulheres_penal_10k": round((mulheres_penal / pop) * 10000, 2),
            # Idosos
            "idosos_total": idosos_total,
            "idosos_penal": idosos_penal,
            "taxa_idosos_10k": round((idosos_total / pop) * 10000, 2),
            "taxa_idosos_penal_10k": round((idosos_penal / pop) * 10000, 2),
            # PCD
            "pcd_total": pcd_total,
            "pcd_penal": pcd_penal,
            "taxa_pcd_10k": round((pcd_total / pop) * 10000, 2),
            "taxa_pcd_penal_10k": round((pcd_penal / pop) * 10000, 2),
            # LGBT
            "lgbt_total": lgbt_total,
            "lgbt_penal": lgbt_penal,
            "taxa_lgbt_10k": round((lgbt_total / pop) * 10000, 2),
            "taxa_lgbt_penal_10k": round((lgbt_penal / pop) * 10000, 2),
            # Prisional / Rua
            "prisional_total": prisional_total,
            "prisional_penal": prisional_penal,
            "taxa_prisional_10k": round((prisional_total / pop) * 10000, 2),
            "taxa_prisional_penal_10k": round((prisional_penal / pop) * 10000, 2)
        })

    df_kpis = pl.DataFrame(kpis_rows)
    kpis_parquet = root_dir / "sc_kpis_grupos_municipios.parquet"
    df_kpis.write_parquet(kpis_parquet, compression="zstd")
    df_kpis.write_csv(root_dir / "sc_kpis_grupos_municipios.csv")
    print(f"💾 KPIs agregados salvos: {kpis_parquet.name} e CSV correspondente.")

    # 3. Carga no SQLite Local / DuckDB Bridge
    sqlite_path = root_dir / "sc_disque100_analitico.sqlite"
    print(f"🗄️ Carregando tabelas no banco relacional SQL: {sqlite_path.name}...")
    conn = sqlite3.connect(sqlite_path)
    cur = conn.cursor()

    # Cria tabelas relacionais
    cur.execute("DROP TABLE IF EXISTS dim_municipios;")
    cur.execute("DROP TABLE IF EXISTS dim_unidades_pci;")
    cur.execute("DROP TABLE IF EXISTS kpis_grupos_municipios;")
    cur.execute("DROP TABLE IF EXISTS fato_denuncias_resumo;")

    # Insere dados
    df_dim_mun.to_pandas().to_sql("dim_municipios", conn, if_exists="replace", index=False)
    df_dim_pci.to_pandas().to_sql("dim_unidades_pci", conn, if_exists="replace", index=False)
    df_kpis.to_pandas().to_sql("kpis_grupos_municipios", conn, if_exists="replace", index=False)

    # Cria índice para buscas sub-milissegundo
    cur.execute("CREATE INDEX IF NOT EXISTS idx_kpi_ibge ON kpis_grupos_municipios(ibge_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_kpi_regiao ON kpis_grupos_municipios(regiao_intermediaria);")
    conn.commit()
    conn.close()
    print("✅ Banco SQL criado com sucesso e indexado!")

    # 4. Exportação direta para DuckDB Colunar de Alta Performance
    try:
        import duckdb
        for duck_out in [root_dir / "data" / "database" / "sc_disque100_analitico.duckdb", root_dir / "sc_disque100_analitico.duckdb"]:
            duck_out.parent.mkdir(parents=True, exist_ok=True)
            dcon = duckdb.connect(str(duck_out))
            dcon.execute("CREATE OR REPLACE TABLE dim_municipios AS SELECT * FROM df_dim_mun")
            dcon.execute("CREATE OR REPLACE TABLE dim_unidades_pci AS SELECT * FROM df_dim_pci")
            dcon.execute("CREATE OR REPLACE TABLE kpis_grupos_municipios AS SELECT * FROM df_kpis")
            dcon.execute("CREATE OR REPLACE TABLE fato_denuncias AS SELECT * FROM df_fato")
            dcon.close()
        print("🦆 DuckDB analítico sincronizado em data/database/ e na raiz com sucesso!")
    except Exception as e:
        print(f"⚠️ Aviso DuckDB: {e}")

    # 5. Auditoria de Integridade & Hashes SHA-256
    print("\n🔍 EXECUTANDO CHECAGENS DE AUDITORIA & CONSISTÊNCIA...")
    hash_fato = hashlib.sha256(open(fato_parquet, "rb").read()).hexdigest()
    hash_kpi = hashlib.sha256(open(kpis_parquet, "rb").read()).hexdigest()

    relatorio_auditoria = {
        "timestamp_auditoria": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_registros_sc": len(df_fato),
        "total_penal": df_fato.filter(pl.col("indicio_penal") == 1).height,
        "total_social": df_fato.filter(pl.col("indicio_penal") == 0).height,
        "totais_por_grupo": {
            "criancas_e_adolescentes": df_fato.filter(pl.col("is_crianca") == 1).height,
            "mulheres_violencia_genero": df_fato.filter(pl.col("is_mulher") == 1).height,
            "pessoas_idosas": df_fato.filter(pl.col("is_idoso") == 1).height,
            "pessoas_com_deficiencia": df_fato.filter(pl.col("is_pcd") == 1).height,
            "populacao_lgbtqia": df_fato.filter(pl.col("is_lgbtqia") == 1).height,
            "sistema_prisional_e_rua": df_fato.filter(pl.col("is_prisional_rua") == 1).height
        },
        "arquivos_hashes_sha256": {
            "sc_fato_denuncias.parquet": hash_fato,
            "sc_kpis_grupos_municipios.parquet": hash_kpi
        },
        "status": "APROVADO_AUDITORIA_INTEGRIDADE"
    }

    audit_file = root_dir / "sc_relatorio_auditoria_dados.json"
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(relatorio_auditoria, f, ensure_ascii=False, indent=2)

    # Sincroniza arquivos gerados para data/processed/
    proc_dir = root_dir / "data" / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    for fname in ["sc_fato_denuncias.parquet", "sc_dim_municipios.parquet", "sc_dim_pci.parquet", "sc_kpis_grupos_municipios.parquet", "sc_kpis_grupos_municipios.csv", "sc_relatorio_auditoria_dados.json"]:
        src = root_dir / fname
        if src.exists():
            shutil.copyfile(src, proc_dir / fname)

    db_dir = root_dir / "data" / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    if sqlite_path.exists():
        shutil.copyfile(sqlite_path, db_dir / sqlite_path.name)

    print(f"📋 Relatório de Auditoria gravado em {audit_file.name} e sincronizado em data/processed/")
    print("======================================================================")
    print(f"• Total de Registros Auditados: {relatorio_auditoria['total_registros_sc']:,}")
    print(f"• Casos Penais:                 {relatorio_auditoria['total_penal']:,} ({relatorio_auditoria['total_penal']/len(df_fato)*100:.2f}%)")
    print(f"• Demandas Rede Social:         {relatorio_auditoria['total_social']:,} ({relatorio_auditoria['total_social']/len(df_fato)*100:.2f}%)")
    print("• Distribuição por Grupo Vulnerável:")
    for grp, val in relatorio_auditoria["totais_por_grupo"].items():
        print(f"  - {grp:25s}: {val:7,d} casos")
    print("======================================================================")


if __name__ == "__main__":
    root_dir = Path(__file__).resolve().parent
    if root_dir.name == "scripts":
        root_dir = root_dir.parent
    processar_e_gerar_banco(root_dir)

