#!/usr/bin/env python3
"""
=============================================================================
KPIs do Disque 100 por municipio, ano e semestre
=============================================================================
Materializa `kpis_grupos_municipios_ano` a partir de `fato_denuncias`, na
mesma granularidade dos filtros do painel.

Em relacao a versao anterior:
  - a chave inclui `semestre`, para que anos incompletos (2026 tem apenas o
    primeiro semestre) sejam visiveis na propria tabela em vez de aparecerem
    como queda de demanda;
  - acrescenta `denuncias_unicas`, contagem distinta do identificador oficial
    da denuncia, disponivel de 2020/2 em diante;
  - acrescenta `sem_grupo_total` e `sem_grupo_penal`, os registros que nao
    pertencem a nenhum dos seis grupos vulneraveis e que antes desapareciam da
    aba de grupos;
  - registra `registros_com_denuncia_identificavel`, que permite ao painel
    saber quando a metrica de denuncias unicas e aplicavel ao recorte.

Requer que `scripts/gerar_banco_duckdb_sc.py` tenha sido executado antes.
=============================================================================
"""

from pathlib import Path

import duckdb

GRUPOS = (
    ("criancas", "is_crianca"),
    ("mulheres", "is_mulher"),
    ("idosos", "is_idoso"),
    ("pcd", "is_pcd"),
    ("lgbt", "is_lgbtqia"),
    ("prisional", "is_prisional_rua"),
)


def _colunas_grupos() -> str:
    partes = []
    for prefixo, flag in GRUPOS:
        partes.append(f"SUM(f.{flag}) AS {prefixo}_total")
        partes.append(
            f"SUM(CASE WHEN f.{flag} = 1 THEN f.indicio_penal ELSE 0 END) AS {prefixo}_penal"
        )
    return ",\n        ".join(partes)


def build_annual_kpis() -> None:
    root = Path(__file__).resolve().parent.parent
    db_candidates = [
        root / "data" / "database" / "sc_disque100_analitico.duckdb",
        root / "sc_disque100_analitico.duckdb",
    ]
    db_path = next((p for p in db_candidates if p.exists()), None)
    if not db_path:
        raise FileNotFoundError(
            "Base sc_disque100_analitico.duckdb nao encontrada. "
            "Execute scripts/gerar_banco_duckdb_sc.py primeiro."
        )

    con = duckdb.connect(str(db_path))
    print(f"Conectado a {db_path.relative_to(root)}")

    con.execute(f"""
    CREATE OR REPLACE TABLE kpis_grupos_municipios_ano AS
    SELECT
        f.ibge_code,
        f.municipio_nome AS municipio,
        f.regiao_intermediaria,
        f.regiao_imediata,
        m.populacao_censo_2022,
        f.ano,
        f.semestre,
        COUNT(*) AS total_denuncias,
        SUM(f.indicio_penal) AS total_penal,
        COUNT(*) - SUM(f.indicio_penal) AS total_social,
        COUNT(DISTINCT CASE WHEN f.grain_denuncia_confiavel = 1 THEN f.id_denuncia END)
            AS denuncias_unicas,
        COUNT(DISTINCT CASE WHEN f.grain_denuncia_confiavel = 1 AND f.indicio_penal = 1
                            THEN f.id_denuncia END) AS denuncias_unicas_penal,
        SUM(f.grain_denuncia_confiavel) AS registros_com_denuncia_identificavel,
        COALESCE(d.denuncias_unicas_maioria_penal, 0) AS denuncias_unicas_maioria_penal,
        SUM(f.sem_grupo) AS sem_grupo_total,
        SUM(CASE WHEN f.sem_grupo = 1 THEN f.indicio_penal ELSE 0 END) AS sem_grupo_penal,
        {_colunas_grupos()}
    FROM fato_denuncias f
    JOIN dim_municipios m ON f.ibge_code = m.ibge_code
    LEFT JOIN (
        -- Predominancia penal apurada por denuncia: a maioria das violacoes
        -- daquela denuncia e tipificada. Precisa de um agrupamento proprio,
        -- porque nao se deriva de uma soma sobre linhas.
        SELECT ibge_code, ano, semestre,
               SUM(CASE WHEN p * 2 > n THEN 1 ELSE 0 END) AS denuncias_unicas_maioria_penal
        FROM (
            SELECT ibge_code, ano, semestre, id_denuncia,
                   COUNT(*) AS n, SUM(indicio_penal) AS p
            FROM fato_denuncias
            WHERE grain_denuncia_confiavel = 1
            GROUP BY ibge_code, ano, semestre, id_denuncia
        )
        GROUP BY ibge_code, ano, semestre
    ) d ON d.ibge_code = f.ibge_code AND d.ano = f.ano AND d.semestre = f.semestre
    GROUP BY
        f.ibge_code, f.municipio_nome, f.regiao_intermediaria, f.regiao_imediata,
        m.populacao_censo_2022, f.ano, f.semestre, d.denuncias_unicas_maioria_penal
    ORDER BY f.ano, f.semestre, f.municipio_nome;
    """)

    destino = root / "data" / "processed" / "sc_kpis_grupos_municipios_ano.parquet"
    destino.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY kpis_grupos_municipios_ano TO '{destino}' (FORMAT PARQUET)")

    linhas, registros, denuncias, anos = con.execute("""
        SELECT COUNT(*), SUM(total_denuncias), SUM(denuncias_unicas), COUNT(DISTINCT ano)
        FROM kpis_grupos_municipios_ano
    """).fetchone()
    print(
        f"kpis_grupos_municipios_ano: {linhas:,} linhas | "
        f"{registros:,} registros de violacao | "
        f"{denuncias:,} denuncias unicas | {anos} anos"
    )

    incompletos = con.execute("""
        SELECT ano, COUNT(DISTINCT semestre) AS semestres
        FROM kpis_grupos_municipios_ano
        WHERE semestre > 0
        GROUP BY ano HAVING COUNT(DISTINCT semestre) < 2
        ORDER BY ano
    """).fetchall()
    if incompletos:
        detalhe = ", ".join(f"{a} ({s} semestre)" for a, s in incompletos)
        print(f"Anos com cobertura parcial: {detalhe}")

    con.close()


if __name__ == "__main__":
    build_annual_kpis()
