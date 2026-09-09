"""
Módulo de Carregamento e Caching de Dados de Alta Performance.
Integração nativa com DuckDB colunar e fallback ultra-rápido para bases Parquet.
"""

import json
from pathlib import Path
from typing import Tuple, Dict, Any

import pandas as pd
import streamlit as st

try:
    import duckdb
except ImportError:
    duckdb = None


def get_root_dir() -> Path:
    """Detecta de forma resiliente a raiz do projeto."""
    current = Path(__file__).resolve().parent
    if (current.parent / "data").exists():
        return current.parent
    if (current / "data").exists():
        return current
    if (current.parent.parent / "data").exists():
        return current.parent.parent
    return current.parent


@st.cache_data(ttl=3600, show_spinner="Carregando base de dados analítica...")
def carregar_dados() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, Any], Dict[str, Any]]:
    """
    Carrega dados da base única oficial DuckDB com fallback prioritário para Parquet e CSV.
    Retorna DataFrames otimizados em memória cacheados pelo Streamlit.
    """
    root_dir = get_root_dir()
    
    # 1. Tentativa de conexão primária ao DuckDB
    duck_candidates = [
        root_dir / "data" / "database" / "sc_disque100_analitico.duckdb",
        root_dir / "sc_disque100_analitico.duckdb"
    ]
    duck_path = next((p for p in duck_candidates if p.exists()), None)

    df_kpi = pd.DataFrame()
    df_pci = pd.DataFrame()
    df_kpi_ano = pd.DataFrame()

    if duck_path and duckdb:
        try:
            con = duckdb.connect(str(duck_path), read_only=True)
            df_kpi = con.execute("SELECT * FROM kpis_grupos_municipios").fetchdf()
            df_pci = con.execute("SELECT * FROM dim_unidades_pci").fetchdf()
            try:
                df_kpi_ano = con.execute("SELECT * FROM kpis_grupos_municipios_ano").fetchdf()
            except Exception:
                df_kpi_ano = pd.DataFrame()
            con.close()
        except Exception as err:
            st.warning(f"Aviso ao consultar DuckDB ({err}). Ativando fallback Parquet.")

    # 2. Fallback prioritário para Parquet (10x mais rápido que CSV)
    if df_kpi.empty:
        kpi_pq_candidates = [
            root_dir / "data" / "processed" / "sc_kpis_grupos_municipios.parquet",
            root_dir / "sc_kpis_grupos_municipios.parquet",
            root_dir / "data" / "processed" / "sc_kpis_grupos_municipios.csv",
            root_dir / "sc_kpis_grupos_municipios.csv"
        ]
        kpi_file = next((p for p in kpi_pq_candidates if p.exists()), None)
        if kpi_file:
            if kpi_file.suffix == ".parquet":
                df_kpi = pd.read_parquet(kpi_file)
            else:
                df_kpi = pd.read_csv(kpi_file)

    if df_pci.empty:
        pci_candidates = [
            root_dir / "data" / "processed" / "sc_dim_pci.parquet",
            root_dir / "sc_dim_pci.parquet"
        ]
        pci_file = next((p for p in pci_candidates if p.exists()), None)
        if pci_file and pci_file.exists():
            df_pci = pd.read_parquet(pci_file)

    if df_kpi_ano.empty:
        ano_candidates = [
            root_dir / "data" / "processed" / "sc_kpis_grupos_municipios_ano.parquet",
            root_dir / "sc_kpis_grupos_municipios_ano.parquet"
        ]
        ano_file = next((p for p in ano_candidates if p.exists()), None)
        if ano_file and ano_file.exists():
            df_kpi_ano = pd.read_parquet(ano_file)

    # 3. Relatório de auditoria de dados e hashes criptográficos SHA-256
    audit_candidates = [
        root_dir / "data" / "processed" / "sc_relatorio_auditoria_dados.json",
        root_dir / "sc_relatorio_auditoria_dados.json"
    ]
    audit_file = next((p for p in audit_candidates if p.exists()), None)
    audit_data = {}
    if audit_file and audit_file.exists():
        try:
            with open(audit_file, "r", encoding="utf-8") as f:
                audit_data = json.load(f)
        except Exception:
            audit_data = {}

    # 4. Matriz oficial de distâncias e unidades forenses da PCI-SC
    pci_dist_candidates = [
        root_dir / "data" / "processed" / "sc_municipios_distancia_pci.json",
        root_dir / "sc_municipios_distancia_pci.json"
    ]
    pci_dist_file = next((p for p in pci_dist_candidates if p.exists()), None)
    pci_dist_map = {}
    if pci_dist_file and pci_dist_file.exists():
        try:
            with open(pci_dist_file, "r", encoding="utf-8") as f:
                pci_dist_map = json.load(f)
        except Exception:
            pci_dist_map = {}

    return df_kpi, df_pci, df_kpi_ano, audit_data, pci_dist_map

