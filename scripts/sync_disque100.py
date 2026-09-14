#!/usr/bin/env python3
"""
=============================================================================
Disque 100 - Pipeline Paralelo de Download Direto, Conversão Parquet e Limpeza
=============================================================================
Funcionalidades:
  1. Identifica arquivos locais: ignora os que já possuem .parquet gerado.
  2. Limpa CSVs antigos que já possuam .parquet correspondente para liberar espaço.
  3. Baixa em paralelo e diretamente os conjuntos faltantes (2022 a 2020 e 2019 a 2011).
  4. Barra de progresso visual em TUI rica (Rich) para cada download individual.
  5. Resiliente a falhas de rede (usa arquivos parciais .part, retentativas e cancelamento com Ctrl+C).
  6. Converte automaticamente para Parquet ultra-otimizado (Polars), valida integridade e apaga o CSV.
=============================================================================
Uso:
  python sync_disque100.py
  python sync_disque100.py --workers 4 --keep-csv
=============================================================================
"""

import sys
import os
import time
import shutil
import zipfile
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

# Importa as rotinas de conversão e validação ultra-otimizadas do csv2parquet.py
try:
    from csv2parquet import convert_csv_to_parquet
except ImportError:
    print("[-] Erro: csv2parquet.py não encontrado no diretório atual.")
    sys.exit(1)

console = Console()

# Catálogo oficial dos links diretos do Disque 100 (redirecionam direto para o CSV)
DATASETS_CATALOG = [
    # Semestrais (2020 a 2022)
    {
        "name": "disque100-segundo-semestre-2022",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/segundo-semestre-de-2022",
        "type": "semestral",
        "year": 2022,
        "semestre": 2
    },
    {
        "name": "disque100-primeiro-semestre-2022",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/primeiro-semestre-de-2022",
        "type": "semestral",
        "year": 2022,
        "semestre": 1
    },
    {
        "name": "disque100-segundo-semestre-2021",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/segundo-semestre-de-2021",
        "type": "semestral",
        "year": 2021,
        "semestre": 2
    },
    {
        "name": "disque100-primeiro-semestre-2021",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/primeiro-semestre-de-2021",
        "type": "semestral",
        "year": 2021,
        "semestre": 1
    },
    {
        "name": "disque100-segundo-semestre-2020",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/segundo-semestre-de-2020",
        "type": "semestral",
        "year": 2020,
        "semestre": 2
    },
    {
        "name": "disque100-primeiro-semestre-2020",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/primeiro-semestre-de-2020",
        "type": "semestral",
        "year": 2020,
        "semestre": 1
    },
    # Anuais (2019 a 2011)
    {
        "name": "disque100-2019",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2019",
        "type": "anual",
        "year": 2019
    },
    {
        "name": "disque100-2018",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2018",
        "type": "anual",
        "year": 2018
    },
    {
        "name": "disque100-2017",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2017",
        "type": "anual",
        "year": 2017
    },
    {
        "name": "disque100-2016",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2016",
        "type": "anual",
        "year": 2016
    },
    {
        "name": "disque100-2015",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2015",
        "type": "anual",
        "year": 2015
    },
    {
        "name": "disque100-2014",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2014",
        "type": "anual",
        "year": 2014
    },
    {
        "name": "disque100-2013",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2013",
        "type": "anual",
        "year": 2013
    },
    {
        "name": "disque100-2012",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2012",
        "type": "anual",
        "year": 2012
    },
    {
        "name": "disque100-2011",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/disque-100-2011",
        "type": "anual",
        "year": 2011
    },
]

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

def create_resilient_session() -> requests.Session:
    """Cria uma sessão requests com timeout configurado e pooling resiliente."""
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    retries = Retry(
        total=2,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def cleanup_converted_csvs(dest_dir: Path) -> int:
    """Procura por CSVs cujo .parquet já existe e os remove para poupar espaço em disco."""
    deleted_count = 0
    freed_bytes = 0
    for parquet_file in dest_dir.glob("*.parquet"):
        csv_file = parquet_file.with_suffix(".csv")
        if csv_file.exists():
            size = csv_file.stat().st_size
            try:
                csv_file.unlink()
                deleted_count += 1
                freed_bytes += size
            except Exception as e:
                console.print(f"[yellow]Não foi possível apagar {csv_file.name}: {e}[/yellow]")
    
    if deleted_count > 0:
        console.print(f"[green] Limpeza concluída:[/green] {deleted_count} CSV(s) já convertidos foram apagados ([bold]{freed_bytes / (1024*1024):.2f} MB liberados[/bold]).")
    return deleted_count

def download_file_resilient(
    session: requests.Session,
    url: str,
    target_path: Path,
    progress: Progress,
    task_id: int,
    max_retries: int = 2
) -> bool:
    """
    Baixa um arquivo de forma resiliente com suporte a arquivos parciais (.part),
    evitando arquivos corrompidos e atualizando a barra de progresso do Rich em tempo real.
    """
    temp_path = target_path.with_suffix(target_path.suffix + ".part")
    
    for attempt in range(1, max_retries + 1):
        try:
            with session.get(url, stream=True, timeout=(8.0, 60.0), allow_redirects=True) as r:
                if r.status_code != 200:
                    if attempt == max_retries:
                        progress.update(task_id, description=f"[red]Erro HTTP {r.status_code}")
                        return False
                    time.sleep(1.5 * attempt)
                    continue

                total_size = int(r.headers.get("content-length", 0))
                progress.update(task_id, total=total_size if total_size > 0 else None, description="[blue]Baixando...")

                with open(temp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=256 * 1024):
                        if chunk:
                            f.write(chunk)
                            progress.update(task_id, advance=len(chunk))

            # Se for um ZIP baixado, extrai o CSV de dentro dele
            if temp_path.name.lower().endswith(".zip.part") or zipfile.is_zipfile(temp_path):
                with zipfile.ZipFile(temp_path, 'r') as zf:
                    csv_members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
                    if csv_members:
                        with zf.open(csv_members[0]) as source, open(target_path, 'wb') as dest:
                            shutil.copyfileobj(source, dest)
                        temp_path.unlink(missing_ok=True)
                    else:
                        temp_path.rename(target_path)
            else:
                temp_path.rename(target_path)

            progress.update(task_id, description="[green]Download Concluído")
            return True

        except Exception as e:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            if attempt == max_retries:
                progress.update(task_id, description=f"[red]Falha: {str(e)[:22]}")
                return False
            time.sleep(1.5 * attempt)

    return False

def process_single_dataset(
    item: Dict,
    dest_dir: Path,
    progress: Progress,
    task_id: int,
    delete_csv_after: bool = True
) -> Tuple[str, str]:
    """Executa o ciclo completo para um dataset: Download Direto -> Conversão -> Limpeza."""
    base_name = item["name"]
    csv_file = dest_dir / f"{base_name}.csv"
    parquet_file = dest_dir / f"{base_name}.parquet"

    # 1. Se o Parquet já existe, ignora
    if parquet_file.exists():
        progress.update(task_id, description="[bold cyan]Já existe (.parquet)", completed=100, total=100)
        return (base_name, "JA_EXISTE")

    session = create_resilient_session()

    # 2. Se o CSV não existe localmente, baixa diretamente
    if not csv_file.exists():
        progress.update(task_id, description="[blue]Conectando...")
        download_target = csv_file

        success = download_file_resilient(session, item["url"], download_target, progress, task_id)
        if not success:
            return (base_name, "ERRO_DOWNLOAD")

    # 3. Converte CSV para Parquet
    progress.update(task_id, description="[magenta]Convertendo Parquet...")
    try:
        convert_csv_to_parquet(
            csv_file=str(csv_file),
            parquet_file=str(parquet_file),
            validate=True
        )
        
        # 4. Apaga o CSV após validação bem sucedida (se configurado)
        if delete_csv_after and csv_file.exists():
            csv_file.unlink(missing_ok=True)
            
        progress.update(task_id, description="[bold green]Concluído e Validado ")
        return (base_name, "SUCESSO")
    except Exception as e:
        progress.update(task_id, description=f"[red]Erro: {str(e)[:20]}")
        return (base_name, f"ERRO_CONVERSAO: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Paralelo de Download Direto, Conversão e Limpeza dos Dados do Disque 100.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-w", "--workers", type=int, default=3, help="Número de downloads simultâneos (padrão: 3 para evitar rate-limit).")
    parser.add_argument("--keep-csv", action="store_true", help="Não apaga os arquivos CSV após a conversão.")
    parser.add_argument("-dir", "--directory", default=".", help="Diretório de trabalho onde os arquivos serão salvos (padrão: atual).")

    args = parser.parse_args()
    dest_dir = Path(args.directory).resolve()

    console.print(Panel.fit(
        "[bold cyan]DISQUE 100 - SINCRONIZADOR & CONVERSOR PARQUET ULTRA-OTIMIZADO[/bold cyan]\n"
        "[dim]Download Direto Resiliente + Conversão Polars + Validação de Integridade + Limpeza Automática[/dim]",
        border_style="cyan"
    ))

    # 1. Limpa CSVs que já foram convertidos previamente para poupar espaço
    console.print("[bold]1. Checando arquivos locais e limpando CSVs já convertidos...[/bold]")
    cleanup_converted_csvs(dest_dir)

    # 2. Mapeia itens faltantes
    pending_items = []
    already_done = []

    for item in DATASETS_CATALOG:
        pq_path = dest_dir / f"{item['name']}.parquet"
        if pq_path.exists():
            already_done.append(item['name'])
        else:
            pending_items.append(item)

    table = Table(title="\nStatus dos Conjuntos de Dados Históricos", border_style="blue")
    table.add_column("Dataset", style="bold")
    table.add_column("Tipo", style="cyan")
    table.add_column("Status Atual", style="green")

    for item in DATASETS_CATALOG:
        is_done = item['name'] in already_done
        status = "[green]Pronto (.parquet)[/green]" if is_done else "[yellow]Pendente (a baixar/converter)[/yellow]"
        table.add_row(item['name'], item['type'].capitalize(), status)

    console.print(table)

    if not pending_items:
        console.print("\n[bold green]Todos os datasets do Disque 100 já foram baixados e convertidos para Parquet![/bold green]")
        return

    console.print(f"\n[bold yellow]Processando {len(pending_items)} conjuntos faltantes em paralelo ({args.workers} workers)...[/bold yellow]\n")

    # 3. Executa downloads e conversões em paralelo com Barras de Progresso TUI e tratamento gracioso de Ctrl+C
    executor = ThreadPoolExecutor(max_workers=args.workers)
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[name]:<36}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            TextColumn("[dim]{task.description}"),
            console=console
        ) as progress:
            
            task_map = {}
            for item in pending_items:
                t_id = progress.add_task("Aguardando...", name=item['name'], total=None)
                task_map[item['name']] = t_id

            futures = {
                executor.submit(
                    process_single_dataset,
                    item,
                    dest_dir,
                    progress,
                    task_map[item['name']],
                    delete_csv_after=not args.keep_csv
                ): item for item in pending_items
            }

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    item = futures[future]
                    progress.update(task_map[item['name']], description=f"[red]Erro: {e}")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrompido pelo usuário (Ctrl+C). Cancelando tarefas com segurança...[/bold yellow]")
        executor.shutdown(wait=False, cancel_futures=True)
        # Limpa arquivos temporários .part incompletos
        for part_file in dest_dir.glob("*.part"):
            try:
                part_file.unlink(missing_ok=True)
            except Exception:
                pass
        os._exit(0)
    finally:
        executor.shutdown(wait=False)

    # Limpeza final preventiva
    cleanup_converted_csvs(dest_dir)
    console.print("\n[bold green]Processo finalizado![/bold green]")

if __name__ == "__main__":
    main()
