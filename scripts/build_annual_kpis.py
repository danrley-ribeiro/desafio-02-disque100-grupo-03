#!/usr/bin/env python3
"""
Gera a tabela analítica de KPIs anuais por município e grupos vulneráveis
a partir da tabela fato_denuncias em DuckDB.
"""
from pathlib import Path
import duckdb

def build_annual_kpis():
    root = Path(__file__).resolve().parent.parent
    db_candidates = [
        root / "data" / "database" / "sc_disque100_analitico.duckdb",
        root / "sc_disque100_analitico.duckdb"
    ]
    db_path = next((p for p in db_candidates if p.exists()), None)
    if not db_path:
        raise FileNotFoundError("Base DuckDB sc_disque100_analitico.duckdb não encontrada.")

    con = duckdb.connect(str(db_path))
    print(f"📊 Conectado a {db_path}...")

    con.execute("""
    CREATE OR REPLACE TABLE kpis_grupos_municipios_ano AS
    SELECT 
        f.ibge_code,
        f.municipio_nome as municipio,
        f.regiao_intermediaria,
        f.regiao_imediata,
        m.populacao_censo_2022,
        f.ano,
        COUNT(*) as total_denuncias,
        SUM(f.indicio_penal) as total_penal,
        COUNT(*) - SUM(f.indicio_penal) as total_social,
        SUM(f.is_crianca) as criancas_total,
        SUM(CASE WHEN f.is_crianca = 1 THEN f.indicio_penal ELSE 0 END) as criancas_penal,
        SUM(f.is_mulher) as mulheres_total,
        SUM(CASE WHEN f.is_mulher = 1 THEN f.indicio_penal ELSE 0 END) as mulheres_penal,
        SUM(f.is_idoso) as idosos_total,
        SUM(CASE WHEN f.is_idoso = 1 THEN f.indicio_penal ELSE 0 END) as idosos_penal,
        SUM(f.is_pcd) as pcd_total,
        SUM(CASE WHEN f.is_pcd = 1 THEN f.indicio_penal ELSE 0 END) as pcd_penal,
        SUM(f.is_lgbtqia) as lgbt_total,
        SUM(CASE WHEN f.is_lgbtqia = 1 THEN f.indicio_penal ELSE 0 END) as lgbt_penal,
        SUM(f.is_prisional_rua) as prisional_total,
        SUM(CASE WHEN f.is_prisional_rua = 1 THEN f.indicio_penal ELSE 0 END) as prisional_penal
    FROM fato_denuncias f
    JOIN dim_municipios m ON f.ibge_code = m.ibge_code
    GROUP BY f.ibge_code, f.municipio_nome, f.regiao_intermediaria, f.regiao_imediata, m.populacao_censo_2022, f.ano
    ORDER BY f.ano, f.municipio_nome;
    """)

    out_parquet = root / "sc_kpis_grupos_municipios_ano.parquet"
    con.execute(f"COPY kpis_grupos_municipios_ano TO '{out_parquet}' (FORMAT PARQUET)")
    
    processed_dir = root / "data" / "processed"
    if processed_dir.exists():
        con.execute(f"COPY kpis_grupos_municipios_ano TO '{processed_dir / 'sc_kpis_grupos_municipios_ano.parquet'}' (FORMAT PARQUET)")

    cnt = con.execute("SELECT COUNT(*) FROM kpis_grupos_municipios_ano").fetchone()[0]
    sum_tot = con.execute("SELECT SUM(total_denuncias) FROM kpis_grupos_municipios_ano").fetchone()[0]
    print(f"✅ kpis_grupos_municipios_ano gerado com sucesso! Linhas: {cnt}, Total denúncias: {sum_tot}")
    con.close()

if __name__ == "__main__":
    build_annual_kpis()

