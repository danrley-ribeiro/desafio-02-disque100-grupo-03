#!/usr/bin/env python3
"""
=============================================================================
Amostragem Aleatória e Consolidação das Bases Parquet do Disque 100
=============================================================================
Lê todas as 22 bases Parquet do Disque 100 (2011 a 2026), realiza uma amostragem
aleatória estratificada proporcional ao volume de cada período, une os registros
em um único DataFrame consolidado e descarta todas as colunas que estiverem
100% vazias (nulas ou sem conteúdo).

Uso:
  python gerar_amostra_parquet_csv.py
  python gerar_amostra_parquet_csv.py --sample-size 500 --output disque100_amostra_500.csv
=============================================================================
"""

import os
import glob
import time
import random
import argparse
from pathlib import Path
from typing import List, Tuple

import polars as pl
import pyarrow.parquet as pq


def sample_parquet_bases(
    parquet_dir: Path,
    sample_size: int = 500,
    seed: int = 42,
    output_csv: Path = None,
    include_source_file: bool = False
) -> pl.DataFrame:
    """
    Realiza amostragem aleatória proporcional em todas as bases Parquet,
    unifica os registros e remove colunas 100% vazias.
    """
    t0 = time.time()
    files = sorted(glob.glob(str(parquet_dir / "disque100-*.parquet")))
    if not files:
        raise FileNotFoundError(f"Nenhum arquivo 'disque100-*.parquet' encontrado em: {parquet_dir}")

    print(f"1. Mapeando {len(files)} arquivos Parquet do Disque 100...")
    file_counts: List[Tuple[str, int]] = []
    for f in files:
        meta = pq.ParquetFile(f).metadata
        file_counts.append((f, meta.num_rows))

    total_rows = sum(c[1] for c in file_counts)
    print(f"   Total acumulado no acervo histórico: {total_rows:,} registros.")

    # Alocação proporcional de amostras por arquivo
    allocated: List[Tuple[str, int, int]] = []
    for f, cnt in file_counts:
        k = max(1, round(sample_size * (cnt / total_rows)))
        allocated.append((f, cnt, k))

    # Ajuste de arredondamento para somar exatamente sample_size
    diff = sample_size - sum(a[2] for a in allocated)
    if diff != 0:
        max_idx = max(range(len(allocated)), key=lambda i: allocated[i][1])
        allocated[max_idx] = (allocated[max_idx][0], allocated[max_idx][1], allocated[max_idx][2] + diff)

    print(f"2. Sorteando {sample_size} registros aleatórios (Seed: {seed})...")
    random.seed(seed)
    sampled_dfs: List[pl.DataFrame] = []

    for f, cnt, k in allocated:
        fname = Path(f).name
        pf = pq.ParquetFile(f)
        num_rg = pf.num_row_groups
        indices = sorted(random.sample(range(cnt), k))
        
        rg_rows = [pf.metadata.row_group(i).num_rows for i in range(num_rg)]
        rg_offsets = []
        curr = 0
        for r in rg_rows:
            rg_offsets.append((curr, curr + r))
            curr += r

        # Carrega apenas os Row Groups estritamente necessários para velocidade máxima
        needed_rgs = set()
        for idx in indices:
            for rgi, (start, end) in enumerate(rg_offsets):
                if start <= idx < end:
                    needed_rgs.add(rgi)
                    break

        tables = [pf.read_row_group(rgi) for rgi in sorted(needed_rgs)]
        sub_df = pl.concat([pl.from_arrow(t) for t in tables])

        local_indices = []
        for idx in indices:
            pos = 0
            for rgi in sorted(needed_rgs):
                start, end = rg_offsets[rgi]
                if start <= idx < end:
                    local_indices.append(pos + (idx - start))
                    break
                pos += (end - start)

        sampled_slice = sub_df[local_indices]
        if include_source_file:
            sampled_slice = sampled_slice.with_columns(pl.lit(fname).alias("_arquivo_origem"))

        # Converte todas as colunas para Utf8 para garantir união segura sem conflitos de schema
        sampled_slice = sampled_slice.select([
            pl.col(col).cast(pl.Utf8).alias(col) for col in sampled_slice.columns
        ])
        sampled_dfs.append(sampled_slice)

    print("3. Unindo todas as bases amostradas (diagonal concat)...")
    combined = pl.concat(sampled_dfs, how="diagonal")
    print(f"   DataFrame preliminar: {len(combined)} linhas x {len(combined.columns)} colunas.")

    print("4. Excluindo colunas vazias...")
    empty_columns = []
    valid_columns = []

    for col in combined.columns:
        s = combined[col]
        if s.is_null().all():
            empty_columns.append(col)
            continue
        
        non_nulls = s.filter(s.is_not_null())
        non_blanks = non_nulls.filter(
            (non_nulls.str.strip_chars() != "") &
            (~non_nulls.str.to_lowercase().is_in(["null", "none", "nan", "n/a", "n/d", ""]))
        )
        if len(non_blanks) == 0:
            empty_columns.append(col)
        else:
            valid_columns.append(col)

    df_final = combined.select(valid_columns)
    print(f"   Colunas vazias removidas ({len(empty_columns)}): {empty_columns}")
    print(f"   Colunas preservadas com dados ({len(valid_columns)}): {len(valid_columns)} colunas.")

    if output_csv:
        output_csv = Path(output_csv)
        df_final.write_csv(output_csv)
        file_size_kb = output_csv.stat().st_size / 1024
        print(f"5. Arquivo CSV gravado com sucesso: '{output_csv.name}' ({file_size_kb:.1f} KB)")

    print(f"⏱ Tempo total de processamento: {time.time() - t0:.2f} segundos.")
    return df_final


def main():
    parser = argparse.ArgumentParser(description="União e amostragem aleatória das bases Parquet do Disque 100.")
    parser.add_argument("--dir", default=".", help="Diretório contendo os arquivos Parquet (padrão: atual)")
    parser.add_argument("--sample-size", type=int, default=500, help="Quantidade de registros aleatórios (padrão: 500)")
    parser.add_argument("--seed", type=int, default=42, help="Semente de aleatoriedade (padrão: 42)")
    parser.add_argument("--output", default="disque100_amostra_500.csv", help="Caminho do arquivo CSV de saída")
    parser.add_argument("--include-source", action="store_true", help="Inclui coluna indicando o arquivo Parquet de origem")

    args = parser.parse_args()
    sample_parquet_bases(
        parquet_dir=Path(args.dir).resolve(),
        sample_size=args.sample_size,
        seed=args.seed,
        output_csv=Path(args.output).resolve(),
        include_source_file=args.include_source
    )


if __name__ == "__main__":
    main()

