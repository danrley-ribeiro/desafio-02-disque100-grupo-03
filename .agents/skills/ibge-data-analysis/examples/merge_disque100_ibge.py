#!/usr/bin/env python3
"""
=============================================================================
Exemplo Prático: Análise do Disque 100 em Santa Catarina (SC) com IBGE
=============================================================================
Filtra os microdados nacionais do Disque 100 para o estado de Santa Catarina (SC),
cruza com a API de Localidades do IBGE e agrupa denúncias por Município e
Região Intermediária (Florianópolis, Joinville, Chapecó, Blumenau, etc.).
=============================================================================
"""

import requests
import polars as pl
from pathlib import Path

def main():
    print("1. Obtendo metadados dos 295 municípios de Santa Catarina (SC / 42) via IBGE...")
    url_ibge = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/42/municipios?view=nivelado"
    ibge_raw = requests.get(url_ibge).json()

    df_ibge_sc = pl.DataFrame(ibge_raw).select([
        pl.col("municipio-id").cast(pl.Utf8).alias("ibge_code"),
        pl.col("municipio-nome").alias("nome_municipio"),
        pl.col("regiao-intermediaria-nome").alias("regiao_intermediaria"),
        pl.col("regiao-imediata-nome").alias("regiao_imediata"),
        pl.col("mesorregiao-nome").alias("mesorregiao")
    ])
    print(f"   Metadados carregados: {df_ibge_sc.height} municípios de Santa Catarina.")

    # 2. Carrega um arquivo Parquet do Disque 100 se existir
    parquet_path = Path("disque100-primeiro-semestre-2026.parquet")
    if not parquet_path.exists():
        print(f"[-] Arquivo {parquet_path} não encontrado no diretório.")
        return

    print(f"2. Lendo microdados de {parquet_path.name} e filtrando Santa Catarina...")
    # No Disque 100, o código de SC começa com '42' (ex: '4205407 | FLORIANOPOLIS')
    df_disque = (
        pl.read_parquet(parquet_path)
        .with_columns(
            pl.col("Município").str.slice(0, 7).alias("ibge_code")
        )
        .filter(pl.col("ibge_code").str.starts_with("42"))
    )

    print(f"   Denúncias encontradas em Santa Catarina: {df_disque.height:,} registros.")

    print("3. Cruzando denúncias de SC com a hierarquia geográfica oficial do IBGE...")
    df_enriquecido_sc = df_disque.join(df_ibge_sc, on="ibge_code", how="inner")

    print("\n" + "=" * 70)
    print(" 📊 DENÚNCIAS POR REGIÃO INTERMEDIÁRIA DE SANTA CATARINA")
    print("=" * 70)
    agregado_intermed = (
        df_enriquecido_sc
        .group_by("regiao_intermediaria")
        .agg(pl.len().alias("total_denuncias"))
        .sort("total_denuncias", descending=True)
    )
    print(agregado_intermed)

    print("\n" + "=" * 70)
    print(" 🏆 TOP 10 MUNICÍPIOS COM MAIS REGISTROS EM SANTA CATARINA")
    print("=" * 70)
    top_municipios = (
        df_enriquecido_sc
        .group_by(["nome_municipio", "regiao_imediata"])
        .agg(pl.len().alias("total_denuncias"))
        .sort("total_denuncias", descending=True)
        .head(10)
    )
    print(top_municipios)

if __name__ == "__main__":
    main()
