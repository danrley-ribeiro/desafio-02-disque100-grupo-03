#!/usr/bin/env python3
"""
=============================================================================
Disque 100 - Sincronizador de Balanços Gerais Temáticos (2011 a 2019)
=============================================================================
Mapeia e processa automaticamente as 148 tabelas estatísticas temáticas:
  1. Igualdade Racial (2015 a 2019)
  2. Pessoas em Restrição de Liberdade (2013 a 2019)
  3. Balanço Geral Consolidado (2011 a 2019)
  4. Crianças e Adolescentes (2011 a 2019)
  5. Pessoa com Deficiência (2011 a 2019)
  6. Pessoa Idosa (2011 a 2019)
  7. Pessoa em Situação de Rua (2011 a 2019)
  8. População LGBT (2011 a 2019)
  9. Outros (2011 a 2019)
=============================================================================
Recursos:
  - Descoberta dinâmica de todas as 148 tabelas CSV nas 9 páginas temáticas.
  - Organização estruturada em subpastas ou pasta dedicada (ex: balancos-gerais/).
  - Download paralelo com barras de progresso TUI ricas.
  - Conversão instantânea para Parquet ultra-otimizado (Polars) e limpeza de CSVs.
=============================================================================
Uso:
  python sync_balancos.py
  python sync_balancos.py --workers 4 --output-dir balancos-gerais
=============================================================================
"""

import sys
import os
import re
import time
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
from urllib.parse import urljoin
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

# Importa o conversor ultra-otimizado
try:
    from csv2parquet import convert_csv_to_parquet
except ImportError:
    print("[-] Erro: csv2parquet.py não encontrado no diretório atual.")
    sys.exit(1)

console = Console()

THEME_PAGES = [
    {
        "theme": "igualdade-racial",
        "title": "Igualdade Racial (2015-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2015-a-2019-igualdade-racial"
    },
    {
        "theme": "restricao-liberdade",
        "title": "Restrição de Liberdade (2013-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2013-a-2019-pessoas-em-restricao-de-liberdade"
    },
    {
        "theme": "geral",
        "title": "Balanço Geral Consolidado (2011-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2011-a-2019"
    },
    {
        "theme": "criancas-adolescentes",
        "title": "Crianças e Adolescentes (2011-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2011-a-2019-criancas-e-adolescentes"
    },
    {
        "theme": "pessoa-deficiencia",
        "title": "Pessoa com Deficiência (2011-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2011-a-2019-pessoa-com-deficiencia"
    },
    {
        "theme": "pessoa-idosa",
        "title": "Pessoa Idosa (2011-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2011-a-2019-pessoa-idosa"
    },
    {
        "theme": "situacao-de-rua",
        "title": "Pessoa em Situação de Rua (2011-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2011-a-2019-pessoa-em-situacao-de-rua"
    },
    {
        "theme": "populacao-lgbt",
        "title": "População LGBT (2011-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2011-a-2019-populacao-lgbt"
    },
    {
        "theme": "outros",
        "title": "Outros Segmentos (2011-2019)",
        "url": "https://www.gov.br/mdh/pt-br/acesso-a-informacao/dados-abertos/disque100/balanco-geral-2011-a-2019-outros"
    },
]

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
}

def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    retries = Retry(total=2, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def discover_theme_tables(theme_item: Dict, session: requests.Session) -> List[Dict]:
    """Varre a página do tema para extrair os links de todas as tabelas CSV."""
    url = theme_item["url"]
    theme = theme_item["theme"]
    tables = []
    try:
        resp = session.get(url, timeout=12)
        if resp.status_code != 200:
            return tables

        # Extrai links href que apontam para .csv
        matches = re.findall(r'<a[^>]+href=[\"\']([^\"\']+\.csv(?:/view)?)[\"\'][^>]*>(.*?)</a>', resp.text, re.IGNORECASE | re.DOTALL)
        seen = set()
        for href, title in matches:
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            full_view_url = urljoin(url, href)
            # Link direto de download no Plone
            download_url = full_view_url.replace('/view', '').rstrip('/') + '/@@download/file'
            
            # Nome base do arquivo
            filename = full_view_url.replace('/view', '').split('/')[-1]
            if not filename.endswith('.csv'):
                filename += '.csv'
            base_name = filename.replace('.csv', '')

            if base_name in seen:
                continue
            seen.add(base_name)

            tables.append({
                "theme": theme,
                "theme_title": theme_item["title"],
                "base_name": f"{theme}_{base_name}",
                "clean_title": clean_title or base_name,
                "download_url": download_url
            })
    except Exception as e:
        console.print(f"[yellow]Erro ao varrer página do tema '{theme}': {e}[/yellow]")

    return tables

def download_and_convert_table(
    table_info: Dict,
    output_dir: Path,
    progress: Progress,
    task_id: int,
    session: requests.Session,
    keep_csv: bool = False
) -> Tuple[str, str]:
    """Baixa a tabela CSV individual, converte para Parquet e apaga o CSV."""
    base_name = table_info["base_name"]
    theme_subfolder = output_dir / table_info["theme"]
    theme_subfolder.mkdir(parents=True, exist_ok=True)

    csv_path = theme_subfolder / f"{base_name}.csv"
    parquet_path = theme_subfolder / f"{base_name}.parquet"

    # Se o Parquet já existe, pula
    if parquet_path.exists():
        progress.update(task_id, description="[bold cyan]Já existe (.parquet)", completed=100, total=100)
        return (base_name, "JA_EXISTE")

    temp_path = csv_path.with_suffix(".csv.part")
    
    # 1. Download
    try:
        with session.get(table_info["download_url"], stream=True, timeout=(6.0, 30.0), allow_redirects=True) as r:
            if r.status_code != 200:
                progress.update(task_id, description=f"[red]Erro HTTP {r.status_code}")
                return (base_name, f"HTTP_{r.status_code}")

            total_size = int(r.headers.get("content-length", 0))
            progress.update(task_id, total=total_size if total_size > 0 else None, description="[blue]Baixando...")

            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
                        progress.update(task_id, advance=len(chunk))

        temp_path.rename(csv_path)
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        progress.update(task_id, description=f"[red]Falha download: {str(e)[:15]}")
        return (base_name, f"ERRO_DOWNLOAD: {e}")

    # 2. Conversão para Parquet via Polars
    progress.update(task_id, description="[magenta]Convertendo Parquet...")
    try:
        convert_csv_to_parquet(
            csv_file=str(csv_path),
            parquet_file=str(parquet_path),
            validate=True
        )

        if not keep_csv and csv_path.exists():
            csv_path.unlink(missing_ok=True)

        progress.update(task_id, description="[bold green]Concluído e Validado ")
        return (base_name, "SUCESSO")
    except Exception as e:
        progress.update(task_id, description=f"[red]Erro conversão: {str(e)[:15]}")
        return (base_name, f"ERRO_CONVERSAO: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Sincronizador e Conversor Parquet de Balanços Gerais Temáticos do Disque 100.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-w", "--workers", type=int, default=4, help="Número de downloads simultâneos (padrão: 4).")
    parser.add_argument("-o", "--output-dir", default="balancos-gerais", help="Diretório onde as tabelas serão salvas (padrão: balancos-gerais).")
    parser.add_argument("--keep-csv", action="store_true", help="Mantém os arquivos CSV após conversão.")

    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        "[bold cyan]DISQUE 100 - BALANÇOS GERAIS TEMÁTICOS (2011 a 2019)[/bold cyan]\n"
        "[dim]Descoberta Dinâmica + Download Paralelo + Conversão Parquet + Validação + Limpeza[/dim]",
        border_style="cyan"
    ))

    session = create_session()

    # 1. Varre as 9 páginas para catalogar todas as tabelas
    console.print("[bold]1. Mapeando tabelas disponíveis nas 9 páginas temáticas...[/bold]")
    all_tables = []
    
    table_summary = Table(title="\nPáginas Temáticas Mapeadas", border_style="blue")
    table_summary.add_column("Tema", style="bold")
    table_summary.add_column("Tabelas Encontradas", style="green", justify="center")

    for theme_item in THEME_PAGES:
        discovered = discover_theme_tables(theme_item, session)
        all_tables.extend(discovered)
        table_summary.add_row(theme_item["title"], f"{len(discovered)} tabelas")

    console.print(table_summary)
    console.print(f"[bold green]Total de tabelas localizadas:[/bold green] [bold]{len(all_tables)} tabelas CSV[/bold].\n")

    # 2. Identifica as que já foram convertidas
    pending_tables = []
    already_done = 0
    for t in all_tables:
        pq_path = output_dir / t["theme"] / f"{t['base_name']}.parquet"
        if pq_path.exists():
            already_done += 1
        else:
            pending_tables.append(t)

    console.print(f" • [cyan]Já convertidas:[/cyan] {already_done} tabelas")
    console.print(f" • [yellow]Pendentes a processar:[/yellow] {len(pending_tables)} tabelas\n")

    if not pending_tables:
        console.print("[bold green]Todas as 148 tabelas temáticas já estão baixadas e convertidas para Parquet![/bold green]")
        return

    console.print(f"[bold yellow]Iniciando processamento paralelo ({args.workers} workers)...[/bold yellow]\n")

    executor = ThreadPoolExecutor(max_workers=args.workers)
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[name]:<42}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            TextColumn("[dim]{task.description}"),
            console=console
        ) as progress:

            task_map = {}
            for t in pending_tables:
                t_id = progress.add_task("Aguardando...", name=t["base_name"][:40], total=None)
                task_map[t["base_name"]] = t_id

            futures = {
                executor.submit(
                    download_and_convert_table,
                    t,
                    output_dir,
                    progress,
                    task_map[t["base_name"]],
                    session,
                    args.keep_csv
                ): t for t in pending_tables
            }

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    t = futures[future]
                    progress.update(task_map[t["base_name"]], description=f"[red]Erro: {e}")

    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrompido pelo usuário (Ctrl+C). Cancelando com segurança...[/bold yellow]")
        executor.shutdown(wait=False, cancel_futures=True)
        for part in output_dir.rglob("*.part"):
            try:
                part.unlink(missing_ok=True)
            except Exception:
                pass
        os._exit(0)
    finally:
        executor.shutdown(wait=False)

    console.print(f"\n[bold green]Processo concluído! Todas as tabelas foram salvas em:[/bold green] [bold cyan]{output_dir}[/bold cyan]")

if __name__ == "__main__":
    main()
