#!/usr/bin/env python3
"""
=============================================================================
Metricas consolidadas da distribuicao penal em Santa Catarina
=============================================================================
Produz os tres artefatos derivados consumidos pelo painel executivo em HTML:

  data/processed/sc_distribuicao_penal_metricas.json
  data/processed/sc_distribuicao_penal_dados.js     (o JSON acima, como global)
  data/processed/sc_ranking_focos_penais.csv

Este script passou a LER a base analitica (`fato_denuncias` e
`kpis_grupos_municipios` no DuckDB) em vez de varrer os 22 arquivos brutos e
reclassificar tudo por conta propria.

O motivo e de correcao, nao de desempenho: havia duas implementacoes
independentes da mesma classificacao penal e da mesma resolucao de municipio,
uma aqui e outra em `gerar_banco_duckdb_sc.py`. Qualquer correcao aplicada a
uma deixava a outra desatualizada, e foi exatamente o que aconteceu: estes
arquivos ficaram publicando numeros de uma versao anterior da classificacao.
Agora ha uma unica fonte de verdade.

Uso:
    python3 scripts/analisar_distribuicao_penal_sc.py
Requer que `scripts/gerar_banco_duckdb_sc.py` tenha sido executado antes.
=============================================================================
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "scripts" else CURRENT_DIR

import duckdb
import pandas as pd

TOPO = 15
# Piso populacional do ranking por taxa. Sem ele o topo e ocupado por
# municipios de poucos milhares de habitantes, cuja taxa oscila em ordens de
# magnitude a cada denuncia.
POP_MINIMA_RANKING = 20_000


def conectar(root_dir: Path) -> duckdb.DuckDBPyConnection:
    caminhos = [
        root_dir / "data" / "database" / "sc_disque100_analitico.duckdb",
        root_dir / "sc_disque100_analitico.duckdb",
    ]
    caminho = next((p for p in caminhos if p.exists()), None)
    if caminho is None:
        raise FileNotFoundError(
            "Base sc_disque100_analitico.duckdb nao encontrada. "
            "Execute scripts/gerar_banco_duckdb_sc.py primeiro."
        )
    print(f"Lendo {caminho.relative_to(root_dir)}")
    return duckdb.connect(str(caminho), read_only=True)


def montar_metricas(con: duckdb.DuckDBPyConnection, auditoria: Dict[str, Any]) -> Dict[str, Any]:
    def df(sql: str) -> pd.DataFrame:
        return con.execute(sql).fetchdf()

    totais = df("""
        SELECT COUNT(*) AS total_registros,
               SUM(indicio_penal) AS total_penal,
               COUNT(*) - SUM(indicio_penal) AS total_social,
               COUNT(DISTINCT CASE WHEN grain_denuncia_confiavel = 1 THEN id_denuncia END)
                   AS total_denuncias_unicas
        FROM fato_denuncias
    """).iloc[0]
    total = int(totais["total_registros"])
    penal = int(totais["total_penal"])

    por_ano_df = df("""
        SELECT ano,
               COUNT(*) AS total,
               SUM(indicio_penal) AS penal,
               COUNT(*) - SUM(indicio_penal) AS social,
               COUNT(DISTINCT CASE WHEN grain_denuncia_confiavel = 1 THEN id_denuncia END)
                   AS denuncias_unicas,
               COUNT(DISTINCT semestre) AS semestres
        FROM fato_denuncias GROUP BY ano ORDER BY ano
    """)
    por_ano = {
        str(int(r["ano"])): {
            "total": int(r["total"]),
            "penal": int(r["penal"]),
            "social": int(r["social"]),
            "denuncias_unicas": int(r["denuncias_unicas"]),
            # Arquivos anuais de 2011 a 2019 vem com semestre 0 e cobrem o ano inteiro.
            "cobertura_parcial": bool(r["semestres"] == 1 and int(r["ano"]) >= 2020),
        }
        for _, r in por_ano_df.iterrows()
    }

    def contagem(coluna: str, filtro: str = "") -> Dict[str, int]:
        onde = f"WHERE {filtro}" if filtro else ""
        d = df(f"SELECT {coluna} AS k, COUNT(*) AS n FROM fato_denuncias {onde} GROUP BY 1 ORDER BY 2 DESC")
        return {str(r["k"]): int(r["n"]) for _, r in d.iterrows()}

    regioes_df = df("""
        SELECT regiao_intermediaria AS regiao,
               COUNT(DISTINCT ibge_code) AS municipios,
               COUNT(*) AS total,
               SUM(indicio_penal) AS penal
        FROM fato_denuncias GROUP BY 1 ORDER BY total DESC
    """)
    pop_regiao = df("""
        SELECT regiao_intermediaria AS regiao, SUM(populacao_censo_2022) AS populacao
        FROM dim_municipios GROUP BY 1
    """).set_index("regiao")["populacao"].to_dict()

    por_regiao = {}
    for _, r in regioes_df.iterrows():
        pop = int(pop_regiao.get(r["regiao"], 0) or 0)
        por_regiao[str(r["regiao"])] = {
            "municipios": int(r["municipios"]),
            "populacao_censo_2022": pop or None,
            "total": int(r["total"]),
            "penal": int(r["penal"]),
            "pct_penal": round(100.0 * r["penal"] / r["total"], 2) if r["total"] else None,
            "taxa_total_10k": round(r["total"] / pop * 10000, 2) if pop else None,
            "taxa_penal_10k": round(r["penal"] / pop * 10000, 2) if pop else None,
        }

    municipios_df = df("""
        SELECT ibge_code, municipio, regiao_intermediaria, regiao_imediata,
               populacao_censo_2022, total_registros, total_penal, total_social,
               denuncias_unicas, denuncias_unicas_maioria_penal,
               taxa_total_10k, taxa_penal_10k
        FROM kpis_grupos_municipios ORDER BY total_registros DESC
    """)

    # Categoria penal predominante de cada municipio, para o ranking de focos.
    predominante = df("""
        SELECT ibge_code, categoria_penal FROM (
            SELECT ibge_code, categoria_penal, COUNT(*) AS n,
                   ROW_NUMBER() OVER (PARTITION BY ibge_code ORDER BY COUNT(*) DESC) AS pos
            FROM fato_denuncias WHERE indicio_penal = 1
            GROUP BY ibge_code, categoria_penal
        ) WHERE pos = 1
    """).set_index("ibge_code")["categoria_penal"].to_dict()
    municipios_df["categoria_penal_predominante"] = municipios_df["ibge_code"].map(predominante)

    elegiveis = municipios_df[municipios_df["populacao_censo_2022"] >= POP_MINIMA_RANKING]
    registros_mun: List[Dict[str, Any]] = json.loads(
        municipios_df.to_json(orient="records", force_ascii=False)
    )

    pci = df("SELECT sigla, nome, municipio, tipo, lat, lon FROM dim_unidades_pci ORDER BY tipo, municipio")

    return {
        "metadata": {
            "gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
            "periodo": auditoria.get("totais", {}).get("periodo"),
            "estado": "Santa Catarina",
            "derivado_de": "fato_denuncias e kpis_grupos_municipios da base analitica",
            "fonte_primaria": "MDHC, microdados abertos do Disque 100",
            "fonte_demografica": "IBGE, Censo Demografico 2022, tabela SIDRA 4714",
            "fonte_seguranca": "Policia Cientifica de Santa Catarina",
            "unidade_padrao": "registros de violacao",
            "advertencia_unidade": (
                auditoria.get("unidade_de_medida", {}).get("advertencia") or ""
            ),
            "piso_populacional_ranking": POP_MINIMA_RANKING,
        },
        "totais_globais": {
            "total_registros": total,
            "total_penal": penal,
            "total_social": total - penal,
            "total_denuncias_unicas": int(totais["total_denuncias_unicas"]),
            "pct_penal": round(100.0 * penal / total, 2) if total else None,
            "pct_social": round(100.0 * (total - penal) / total, 2) if total else None,
        },
        "por_ano": por_ano,
        "por_categoria_penal": contagem("categoria_penal", "indicio_penal = 1"),
        "por_grau_certeza": contagem("grau_certeza"),
        "por_orgao_prioritario": contagem("orgao_prioritario"),
        "por_grupo_primario": contagem("grupo_primario"),
        "por_regiao_intermediaria": por_regiao,
        "municipios": registros_mun,
        "top_maior_taxa_penal_10k": json.loads(
            elegiveis.nlargest(TOPO, "taxa_penal_10k").to_json(orient="records", force_ascii=False)
        ),
        "top_maior_volume_absoluto": json.loads(
            municipios_df.nlargest(TOPO, "total_penal").to_json(orient="records", force_ascii=False)
        ),
        "policia_cientifica_unidades": json.loads(pci.to_json(orient="records", force_ascii=False)),
        "limitacoes_conhecidas": auditoria.get("limitacoes_conhecidas", []),
    }


def main() -> None:
    root_dir = ROOT_DIR
    proc = root_dir / "data" / "processed"
    proc.mkdir(parents=True, exist_ok=True)

    auditoria: Dict[str, Any] = {}
    caminho_auditoria = proc / "sc_relatorio_auditoria_dados.json"
    if caminho_auditoria.exists():
        with open(caminho_auditoria, "r", encoding="utf-8") as f:
            auditoria = json.load(f)

    con = conectar(root_dir)
    try:
        metricas = montar_metricas(con, auditoria)
    finally:
        con.close()

    json_path = proc / "sc_distribuicao_penal_metricas.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=1)

    # O painel executivo em HTML carrega o mesmo conteudo como variavel global,
    # para funcionar aberto direto do disco, sem servidor.
    js_path = proc / "sc_distribuicao_penal_dados.js"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.SC_PENAL_METRICAS = ")
        json.dump(metricas, f, ensure_ascii=False)
        f.write(";\n")

    ranking = pd.DataFrame(metricas["top_maior_taxa_penal_10k"])
    csv_path = proc / "sc_ranking_focos_penais.csv"
    ranking.to_csv(csv_path, index=False, encoding="utf-8")

    # Este e o ultimo passo do pipeline, portanto e aqui que a tabela de hashes
    # do relatorio de auditoria e fechada: so agora todos os artefatos de
    # data/processed/ existem na versao final.
    if auditoria:
        sys.path.insert(0, str(CURRENT_DIR))
        from gerar_banco_duckdb_sc import hashes_processados

        auditoria["arquivos_hashes_sha256"] = hashes_processados(proc)
        auditoria["timestamp_hashes"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(caminho_auditoria, "w", encoding="utf-8") as f:
            json.dump(auditoria, f, ensure_ascii=False, indent=2)
        print(f"  {caminho_auditoria.name}: {len(auditoria['arquivos_hashes_sha256'])} hashes atualizados")

    t = metricas["totais_globais"]
    print(f"  {json_path.name} ({json_path.stat().st_size / 1024:.0f} KB)")
    print(f"  {js_path.name} ({js_path.stat().st_size / 1024:.0f} KB)")
    print(f"  {csv_path.name} ({len(ranking)} municipios)")
    print("=" * 70)
    print(f"Registros de violacao   {t['total_registros']:>10,}")
    print(f"  com indicio penal     {t['total_penal']:>10,} ({t['pct_penal']}%)")
    print(f"  demanda social        {t['total_social']:>10,} ({t['pct_social']}%)")
    print(f"Denuncias unicas        {t['total_denuncias_unicas']:>10,}")
    print(f"Ranking por taxa: piso de {POP_MINIMA_RANKING:,} habitantes")
    for i, r in enumerate(metricas["top_maior_taxa_penal_10k"][:5], 1):
        print(f"  {i}. {r['municipio']:<26s} {r['taxa_penal_10k']:>8.1f}/10k  pop {r['populacao_censo_2022']:>8,}")
    print("=" * 70)


if __name__ == "__main__":
    main()
