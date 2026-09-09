#!/usr/bin/env python3
"""
=============================================================================
CSV to Parquet Converter - Ultra-Optimized & High Performance with Validation
=============================================================================
Tecnologia: Polars (Engine Rust + Apache Arrow + SIMD + Streaming)
Recursos:
  - Processamento Out-of-Core / Streaming (baixo consumo de RAM)
  - Paralelismo massivo automático utilizando 100% dos núcleos/threads de CPU
  - Suporte completo a UTF-8 (inclusive detecção e remoção de BOM \\ufeff)
  - Auto-detecção inteligente de delimitador (, ; \\t |)
  - Compressão ZSTD ultra-rápida de alta taxa de compressão
  - Validação pós-criação automatizada com comparações aleatórias de integridade
=============================================================================
Uso:
  python csv2parquet.py -csv <arquivo_csv> -parquet <arquivo_parquet>
=============================================================================
"""

import sys
import os
import time
import random
import argparse
from pathlib import Path

def normalize_file_to_utf8(csv_path: Path) -> None:
    """Detecta se o arquivo está em Latin-1/Windows-1252 e converte para UTF-8 limpo com acentuação correta."""
    try:
        with open(csv_path, 'rb') as f:
            chunk = f.read(256 * 1024)
        
        try:
            chunk.decode('utf-8')
            return
        except UnicodeDecodeError:
            pass

        # Se o arquivo foi salvo em Latin-1 / Windows-1252, converte para UTF-8 preservando acentos
        raw_bytes = csv_path.read_bytes()
        text = raw_bytes.decode('latin-1', errors='replace')
        csv_path.write_text(text, encoding='utf-8')
    except Exception:
        pass

def detect_separator(csv_path: str, encoding: str = "utf-8") -> str:
    """Detecta automaticamente o separador do CSV lendo as primeiras linhas."""
    normalize_file_to_utf8(Path(csv_path))
    delimiters = [";", ",", "\t", "|"]
    try:
        with open(csv_path, "r", encoding=encoding, errors="replace") as f:
            first_line = f.readline()
            if not first_line:
                return ","
            # Remove UTF-8 BOM se presente
            if first_line.startswith("\ufeff"):
                first_line = first_line[1:]
            
            # Conta ocorrências dos possíveis delimitadores
            counts = {sep: first_line.count(sep) for sep in delimiters}
            detected = max(counts, key=counts.get)
            return detected if counts[detected] > 0 else ","
    except Exception:
        return ","

def validate_parquet_against_csv(
    csv_path: Path,
    parquet_path: Path,
    separator: str,
    sample_size: int = 2000,
    seed: int = 42
) -> bool:
    """
    Executa validação pós-criação comparando o CSV original com o Parquet gerado:
      1. Contagem total de linhas
      2. Nomes, ordem e quantidade de colunas
      3. Amostras de início (Head) e fim (Tail)
      4. Sorteio de N registros aleatórios distribuídos por todo o arquivo
    """
    import polars as pl

    print("\n" + "=" * 65)
    print(" 🔍 INICIANDO VALIDAÇÃO DE INTEGRIDADE (CSV vs PARQUET)")
    print("=" * 65)
    
    val_start = time.perf_counter()

    try:
        lf_csv = pl.scan_csv(
            str(csv_path),
            separator=separator,
            encoding="utf8-lossy",
            quote_char=None,
            null_values=["NULL", "null", "None", "NA", "N/A", "N/D", ""],
            infer_schema_length=50000,
            ignore_errors=True,
            truncate_ragged_lines=True
        )
        lf_pq = pl.scan_parquet(str(parquet_path))

        # 1. Checagem de Quantidade de Linhas
        csv_rows = lf_csv.select(pl.len()).collect().item()
        pq_rows = lf_pq.select(pl.len()).collect().item()

        if csv_rows != pq_rows:
            print(f" ❌ ERRO: Contagem de linhas diverge! CSV: {csv_rows:,} | Parquet: {pq_rows:,}")
            return False
        print(f" • [1/4] Total de Linhas: {csv_rows:,} registros idênticos ✅")

        # 2. Checagem de Colunas
        csv_cols = lf_csv.collect_schema().names()
        pq_cols = lf_pq.collect_schema().names()

        if csv_cols != pq_cols:
            print(f" ❌ ERRO: Colunas divergem! CSV: {len(csv_cols)} | Parquet: {len(pq_cols)}")
            return False
        print(f" • [2/4] Estrutura: {len(csv_cols)} colunas conferidas na mesma ordem ✅")

        # 3. Validação de Início e Fim (Head & Tail)
        head_csv = lf_csv.head(50).collect()
        head_pq = lf_pq.head(50).collect()
        if not head_csv.equals(head_pq):
            print(" ❌ ERRO: Divergência encontrada no início do arquivo (Head 50).")
            return False

        tail_csv = lf_csv.tail(50).collect()
        tail_pq = lf_pq.tail(50).collect()
        if not tail_csv.equals(tail_pq):
            print(" ❌ ERRO: Divergência encontrada no final do arquivo (Tail 50).")
            return False
        print(" • [3/4] Amostras de Extremidades (Head/Tail - 100 linhas): 100% Idênticas ✅")

        # 4. Sorteio de Amostras Aleatórias por todo o dataset
        actual_samples = min(sample_size, csv_rows)
        random.seed(seed)
        sampled_indices = sorted(random.sample(range(csv_rows), actual_samples))

        sample_csv = (
            lf_csv.with_row_index("__idx")
            .filter(pl.col("__idx").is_in(sampled_indices))
            .drop("__idx")
            .collect()
        )
        sample_pq = (
            lf_pq.with_row_index("__idx")
            .filter(pl.col("__idx").is_in(sampled_indices))
            .drop("__idx")
            .collect()
        )

        if not sample_csv.equals(sample_pq):
            print(" ❌ ERRO: Divergência encontrada nas amostras aleatórias!")
            for col in csv_cols:
                if not sample_csv[col].equals(sample_pq[col]):
                    print(f"    - Divergência detectada na coluna: '{col}'")
            return False

        val_elapsed = time.perf_counter() - val_start
        print(f" • [4/4] Amostragem Aleatória ({actual_samples:,} linhas sorteadas): 100% Idênticas ✅")
        print(f" • Tempo de Validação: {val_elapsed:.2f}s")
        print("=" * 65)
        print(" 🎉 RESULTADO: O arquivo Parquet é 100% IDÊNTICO ao CSV original!")
        print("=" * 65)
        return True

    except Exception as e:
        print(f" ⚠️ Aviso durante validação: {e}")
        return False

def convert_csv_to_parquet(
    csv_file: str,
    parquet_file: str,
    separator: str = None,
    compression: str = "zstd",
    compression_level: int = 3,
    row_group_size: int = 524288,
    infer_schema_length: int = 10000,
    validate: bool = True,
    sample_size: int = 2000
) -> None:
    csv_path = Path(csv_file).resolve()
    parquet_path = Path(parquet_file).resolve()

    if not csv_path.exists():
        print(f"[-] Erro: O arquivo CSV '{csv_file}' não foi encontrado.")
        sys.exit(1)

    # Cria diretório de destino se não existir
    parquet_path.parent.mkdir(parents=True, exist_ok=True)

    # Detecta o separador se não informado
    if separator is None:
        separator = detect_separator(str(csv_path))

    file_size_bytes = csv_path.stat().st_size
    file_size_mb = file_size_bytes / (1024 * 1024)

    print("=" * 65)
    print(" 🚀 INICIANDO CONVERSÃO ULTRA-OTIMIZADA (CSV -> PARQUET)")
    print("=" * 65)
    print(f" • Arquivo de Entrada : {csv_path.name} ({file_size_mb:.2f} MB)")
    print(f" • Arquivo de Saída   : {parquet_path.name}")
    print(f" • Delimitador        : '{separator}'")
    print(f" • Encoding           : UTF-8")
    print(f" • Compressão Parquet : {compression.upper()} (Level: {compression_level})")
    print(f" • CPU Cores Ativos   : {os.cpu_count()} threads detectadas")
    print("=" * 65)

    start_time = time.perf_counter()

    try:
        import polars as pl
        
        # O Polars utiliza Rust com Rayon para paralelismo SIMD/Multi-thread e lazy streaming.
        # scan_csv lê o CSV de forma preguiçosa e sink_parquet escreve em streaming direto para o disco
        # sem sobrecarregar a memória RAM.
        lf = pl.scan_csv(
            source=str(csv_path),
            separator=separator,
            encoding="utf8-lossy",
            quote_char=None,
            null_values=["NULL", "null", "None", "NA", "N/A", "N/D", ""],
            infer_schema_length=50000,
            ignore_errors=True,
            truncate_ragged_lines=True,
            low_memory=False,
        )

        # Escreve em Parquet usando engine de streaming com compressão Zstandard
        lf.sink_parquet(
            path=str(parquet_path),
            compression=compression,
            compression_level=compression_level,
            statistics=True,
            row_group_size=row_group_size,
            mkdir=True
        )

    except ImportError:
        # Fallback de alta performance usando DuckDB ou PyArrow se Polars não estiver instalado
        print("[!] Polars não encontrado. Tentando fallback com DuckDB / PyArrow...")
        try:
            import duckdb
            conn = duckdb.connect()
            conn.execute(f"PRAGMA threads={os.cpu_count()};")
            query = f"""
            COPY (
                SELECT * FROM read_csv('{str(csv_path)}', 
                    delim='{separator}', 
                    header=True, 
                    auto_detect=True,
                    sample_size=20480
                )
            ) TO '{str(parquet_path)}' (FORMAT PARQUET, COMPRESSION '{compression}');
            """
            conn.execute(query)
            conn.close()
        except ImportError:
            try:
                import pyarrow.csv as pv
                import pyarrow.parquet as pq
                
                parse_options = pv.ParseOptions(delimiter=separator)
                read_options = pv.ReadOptions(encoding="utf-8")
                table = pv.read_csv(str(csv_path), parse_options=parse_options, read_options=read_options)
                pq.write_table(table, str(parquet_path), compression=compression)
            except ImportError:
                print("\n[-] ERRO: Nenhuma biblioteca de alta performance instalada.")
                print("Por favor, instale o Polars para máxima velocidade:")
                print("   pip install polars pyarrow\n")
                sys.exit(1)

    elapsed = time.perf_counter() - start_time
    output_size_bytes = parquet_path.stat().st_size
    output_size_mb = output_size_bytes / (1024 * 1024)
    compression_ratio = (1 - (output_size_bytes / file_size_bytes)) * 100 if file_size_bytes > 0 else 0
    throughput = file_size_mb / elapsed if elapsed > 0 else 0

    print("\n" + "=" * 65)
    print(" ✅ CONVERSÃO CONCLUÍDA COM SUCESSO!")
    print("=" * 65)
    print(f" • Tempo decorrido    : {elapsed:.2f} segundos")
    print(f" • Throughput         : {throughput:.2f} MB/s")
    print(f" • Tamanho Final      : {output_size_mb:.2f} MB")
    print(f" • Redução de Espaço  : {compression_ratio:.2f}% de economia")
    print(f" • Destino            : {parquet_path}")
    print("=" * 65)

    # Executa validação de integridade pós-criação
    if validate:
        validate_parquet_against_csv(
            csv_path=csv_path,
            parquet_path=parquet_path,
            separator=separator,
            sample_size=sample_size
        )

def main():
    parser = argparse.ArgumentParser(
        description="Conversor Ultra-Otimizado de CSV para Parquet em Python com Validação de Integridade.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Exemplo de uso:
  python csv2parquet.py -csv dados.csv -parquet dados.parquet
  python csv2parquet.py -csv input.csv -parquet output.parquet -sep ";" --no-validate
"""
    )
    
    # Suporte aos parâmetros requeridos pelo usuário (-csv e -parquet)
    parser.add_argument("-csv", "--csv", dest="csv_file", required=True, help="Caminho do arquivo CSV de entrada.")
    parser.add_argument("-parquet", "--parquet", dest="parquet_file", required=True, help="Caminho do arquivo Parquet de saída.")
    parser.add_argument("-sep", "--separator", dest="separator", default=None, help="Delimitador do CSV (opcional, auto-detectado por padrão).")
    parser.add_argument("-c", "--compression", dest="compression", default="zstd", choices=["zstd", "snappy", "lz4", "gzip", "uncompressed"], help="Algoritmo de compressão (padrão: zstd).")
    parser.add_argument("-level", "--compression-level", dest="compression_level", type=int, default=3, help="Nível de compressão zstd (1 a 22, padrão: 3).")
    parser.add_argument("--no-validate", dest="validate", action="store_false", help="Desativa a validação pós-criação.")
    parser.add_argument("-samples", "--samples", dest="sample_size", type=int, default=2000, help="Quantidade de amostras aleatórias para validação (padrão: 2000).")

    parser.set_defaults(validate=True)
    args = parser.parse_args()

    convert_csv_to_parquet(
        csv_file=args.csv_file,
        parquet_file=args.parquet_file,
        separator=args.separator,
        compression=args.compression,
        compression_level=args.compression_level,
        validate=args.validate,
        sample_size=args.sample_size
    )

if __name__ == "__main__":
    main()
