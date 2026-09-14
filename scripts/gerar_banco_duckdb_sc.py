#!/usr/bin/env python3
"""
=============================================================================
Gerador do Banco Analitico do Disque 100 em Santa Catarina (2011-2026)
=============================================================================
Le os 22 arquivos de microdados publicados pelo MDHC, filtra Santa Catarina,
classifica cada registro quanto a tipicidade penal e aos grupos vulneraveis, e
materializa a modelagem dimensional consumida pelo painel:

  fato_denuncias ................ registros de violacao classificados
  dim_municipios ................ 295 municipios com Censo 2022 e regioes IBGE
  dim_unidades_pci .............. 30 unidades da Policia Cientifica de SC
  kpis_grupos_municipios ........ agregado por municipio
  kpis_categoria_penal .......... agregado por ano, regiao e categoria penal

UNIDADE DE MEDIDA - leia antes de usar qualquer numero deste banco.
Cada linha dos microdados e uma combinacao violacao x vitima x suspeito, e nao
uma denuncia. Em 2026/1, Santa Catarina tem 95.850 linhas para 13.140 denuncias
distintas. O fator de expansao subiu de 2,3 (2020/2) para 7,3 (2026/1) e varia
de 2 a 17 entre municipios, de modo que contagens de linha nao sao comparaveis
nem no tempo nem no territorio.

Por isso o fato carrega duas granularidades:
  - a linha em si, chamada de REGISTRO DE VIOLACAO;
  - `id_denuncia`, o identificador oficial da denuncia, disponivel a partir de
    2020/2, que permite COUNT(DISTINCT) e e a base da metrica DENUNCIAS UNICAS.
`grain_denuncia_confiavel` marca as linhas em que essa contagem e valida.

Exporta Parquet, SQLite e DuckDB, alem de um relatorio de auditoria com
inventario por arquivo, cobertura de indicadores por semestre, fator de
expansao, comparacao com os balancos oficiais do MDHC e hashes SHA-256.
=============================================================================
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent if CURRENT_DIR.name == "scripts" else CURRENT_DIR
for _p in (str(CURRENT_DIR), str(ROOT_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import polars as pl

from classificar_grupos_vulneraveis import GRUPOS_CANONICOS, classificar_grupos
from classificar_indicio_penal import classificar_caso
from colunas_disque100 import ResolvedorColunas, normalizar_chave
from generate_sc_disque100_folium_dashboard import IBGEClient

# Codigo sentinela para registros cujo municipio nao pode ser identificado.
IBGE_NAO_IDENTIFICADO = "4200000"
NOME_NAO_IDENTIFICADO = "NÃO IDENTIFICADO"

# Esquema do fato, declarado para nao depender da inferencia por amostragem.
ESQUEMA_FATO: Dict[str, Any] = {
    "id_fato": pl.Utf8,
    "ano": pl.Int64,
    "semestre": pl.Int64,
    "arquivo_origem": pl.Utf8,
    "id_denuncia": pl.Utf8,
    "grain_denuncia_confiavel": pl.Int64,
    "ibge_code": pl.Utf8,
    "municipio_nome": pl.Utf8,
    "regiao_intermediaria": pl.Utf8,
    "regiao_imediata": pl.Utf8,
    "indicio_penal": pl.Int64,
    "categoria_penal": pl.Utf8,
    "grau_certeza": pl.Utf8,
    "orgao_prioritario": pl.Utf8,
    "fundamentacao_legal": pl.Utf8,
    "grupo_primario": pl.Utf8,
    "is_crianca": pl.Int64,
    "is_mulher": pl.Int64,
    "is_idoso": pl.Int64,
    "is_pcd": pl.Int64,
    "is_lgbtqia": pl.Int64,
    "is_prisional_rua": pl.Int64,
}

# Rotulos do campo "Grupo vulneravel" do Disque 100 mapeados para os grupos
# canonicos. Serve para declarar, por periodo, quais modulos existiam na base:
# o modulo "Violencia contra a Mulher", por exemplo, so aparece nos microdados
# a partir de 2025, de modo que a serie desse grupo nao e comparavel antes.
PADROES_MODULO: Tuple[Tuple[str, str], ...] = (
    ("CRIANC", "is_crianca"),
    ("ADOLESC", "is_crianca"),
    ("MULHER", "is_mulher"),
    ("IDOS", "is_idoso"),
    ("DEFICIENCIA", "is_pcd"),
    ("LGBT", "is_lgbtqia"),
    ("LIBERDADE", "is_prisional_rua"),
    ("RUA", "is_prisional_rua"),
)


def modulos_declarados(valores: Any) -> List[str]:
    """Grupos canonicos cujos modulos aparecem entre os rotulos informados."""
    achados = set()
    for v in valores:
        alto = str(v or "").upper()
        alto_sem_acento = (
            alto.replace("Ç", "C").replace("Ã", "A").replace("Á", "A")
            .replace("É", "E").replace("Ê", "E").replace("Í", "I")
            .replace("Ó", "O").replace("Õ", "O").replace("Ú", "U")
        )
        for padrao, grupo in PADROES_MODULO:
            if padrao in alto_sem_acento:
                achados.add(grupo)
    return sorted(achados)


# Grupos materializados nos KPIs: prefixo da coluna -> marcacao de origem.
GRUPOS_KPI: Tuple[Tuple[str, str], ...] = (
    ("criancas", "is_crianca"),
    ("mulheres", "is_mulher"),
    ("idosos", "is_idoso"),
    ("pcd", "is_pcd"),
    ("lgbt", "is_lgbtqia"),
    ("prisional", "is_prisional_rua"),
)


# =============================================================================
# 1. Identificacao de municipio
# =============================================================================

def extrair_codigo_municipio(raw_val: Any, name_to_code: Dict[str, str]) -> Optional[str]:
    """
    Extrai o codigo IBGE de sete digitos a partir dos varios formatos usados na
    serie: codigo puro (`4205407`), codigo com rotulo (`4205407 | FLORIANOPOLIS`)
    e nome livre, com ou sem acento e com ou sem o sufixo "(SC)".

    A comparacao por nome usa a chave normalizada, portanto "Icara", "IÇARA" e
    "içara" resolvem para o mesmo municipio. Nomes que nao resolvem devolvem
    None, e o chamador os contabiliza como nao identificados em vez de
    atribui-los a um municipio por aproximacao.
    """
    if raw_val is None:
        return None
    s = str(raw_val).strip()
    if not s or s.upper() in ("NAN", "NULL", "NONE", "<NA>", "NI"):
        return None

    m_code = re.match(r"^(\d{7})", s)
    if m_code and m_code.group(1).startswith("42"):
        return m_code.group(1)
    if s.isdigit() and len(s) == 7 and s.startswith("42"):
        return s

    limpo = re.sub(r"\s*\(SC\)\s*", " ", s, flags=re.IGNORECASE)
    limpo = re.sub(r"^\d+\s*[|/-]\s*", "", limpo).strip()
    chave = normalizar_chave(limpo)
    if not chave:
        return None
    return name_to_code.get(chave)


def classificar_grupos_vulneraveis(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compatibilidade: classifica um registro isolado montando o resolvedor a
    partir das proprias chaves da linha. Em lote, prefira
    `classificar_grupos(row, resolvedor)` com o resolvedor do arquivo.
    """
    return classificar_grupos(row, ResolvedorColunas(row.keys()))


# =============================================================================
# 2. Dimensao da Policia Cientifica
# =============================================================================

_RE_SIGLA_PCI = re.compile(r"(PCI/[A-Z0-9/]+)")


def construir_dim_pci(pci_units: List[Dict[str, Any]]) -> pl.DataFrame:
    """
    Monta a dimensao das unidades da Policia Cientifica a partir do JSON raspado
    do portal oficial.

    A versao anterior lia `sigla`, `nome`, `tipo`, `lat`, `lon` e `jurisdicao`,
    chaves que nao existem no JSON: o arquivo traz `nome_unidade`, `latitude`,
    `longitude` e `vinculacao`. O resultado eram 30 linhas com quatro colunas
    vazias e coordenadas zeradas, e o catalogo do painel saia em branco.

    A composicao real do orgao, derivada do nome de cada unidade, e de
    9 superintendencias regionais e 21 nucleos regionais.
    """
    linhas: List[Dict[str, Any]] = []
    for u in pci_units:
        nome = str(u.get("nome_unidade") or "").strip()
        m = _RE_SIGLA_PCI.search(nome)
        sigla = m.group(1) if m else ""

        if "Superintend" in nome:
            tipo = "Superintendência Regional"
        elif "Núcleo" in nome or "Nucleo" in nome:
            tipo = "Núcleo Regional"
        else:
            tipo = "Unidade Regional"

        servicos = u.get("servicos") or {}
        med = servicos.get("medicina_legal") or {}
        crim = servicos.get("criminalistica") or {}
        iden = servicos.get("identificacao") or {}

        # A raspagem concatenou responsavel e slug de e-mail no campo de
        # vinculacao de algumas unidades. Mantemos apenas a parte que nomeia a
        # superintendencia a que a unidade se subordina.
        vinculacao = str(u.get("vinculacao") or "").strip()
        responsavel = str(u.get("responsavel") or "").strip()
        if responsavel and responsavel in vinculacao:
            vinculacao = vinculacao.split(responsavel)[0].strip()
        vinculacao = re.sub(r"\s+(nr|sr)[a-z]{2,4}$", "", vinculacao, flags=re.IGNORECASE).strip()

        linhas.append({
            "sigla": sigla,
            "nome": nome,
            "municipio": str(u.get("municipio") or "").strip(),
            "ibge_code": str(u.get("ibge_code") or "").strip(),
            "tipo": tipo,
            "lat": float(u.get("latitude") or 0.0),
            "lon": float(u.get("longitude") or 0.0),
            "vinculacao": vinculacao,
            "responsavel": responsavel,
            "email": str(u.get("email") or "").strip(),
            "url_oficial": str(u.get("url_oficial") or "").strip(),
            "rodovia_principal": str(u.get("rodovia_principal") or "").strip(),
            "endereco": str(med.get("endereco") or crim.get("endereco") or "").strip(),
            "telefone": str(med.get("telefone") or crim.get("telefone") or "").strip(),
            "horario_medicina_legal": str(med.get("horario") or "").strip(),
            "horario_criminalistica": str(crim.get("horario") or "").strip(),
            "tem_medicina_legal": bool(med.get("disponivel")),
            "tem_criminalistica": bool(crim.get("disponivel")),
            "tem_identificacao": bool(iden.get("disponivel")),
        })

    return pl.DataFrame(linhas)


# =============================================================================
# 3. Balanco oficial do MDHC, para validacao externa
# =============================================================================

def ler_balanco_oficial_mdh(root_dir: Path) -> Dict[str, Any]:
    """
    Le o numero oficial de DENUNCIAS de Santa Catarina por ano nos balancos
    2011-2019 publicados pelo proprio MDHC, que acompanham o repositorio.

    Serve de ancora externa: e a unica fonte independente disponivel para
    dimensionar a diferenca entre denuncia e registro de violacao no periodo em
    que os microdados nao trazem identificador de denuncia.
    """
    caminho = root_dir / "data" / "raw" / "balancos-gerais" / "geral" / "geral_numero-de-denuncias-por-uf-por-modulo.parquet"
    if not caminho.exists():
        return {"disponivel": False, "motivo": f"arquivo ausente: {caminho.name}"}

    try:
        df = pl.read_parquet(caminho)
        col = df.columns[1]  # primeira coluna de conteudo; a planilha tem cabecalho em banda
        col_total = df.columns[11]
        ano = None
        por_ano: Dict[str, int] = {}
        for row in df.iter_rows(named=True):
            valor = str(row.get(col) or "")
            m = re.search(r"Ano\s+(20\d\d)", valor)
            if m:
                ano = int(m.group(1))
                continue
            if valor.strip().upper() == "SC" and ano is not None:
                bruto = str(row.get(col_total) or "").replace(".", "").replace(",", "").strip()
                if bruto.isdigit():
                    por_ano[str(ano)] = int(bruto)
        return {
            "disponivel": bool(por_ano),
            "fonte": "MDHC, Balanço Geral do Disque 100 de 2011 a 2019: número de denúncias por UF e módulo",
            "arquivo": str(caminho.relative_to(root_dir)),
            "unidade": "denúncias",
            "denuncias_sc_por_ano": por_ano,
            "total_denuncias_sc": sum(por_ano.values()),
        }
    except Exception as err:  # o arquivo e uma planilha convertida; falha nao deve abortar o ETL
        return {"disponivel": False, "motivo": f"falha ao ler: {err}"}


# =============================================================================
# 4. Metadados auxiliares
# =============================================================================

def carregar_dados_auxiliares(root_dir: Path):
    """Carrega Censo 2022, malha administrativa do IBGE e unidades da PCI-SC."""
    pop_candidates = [
        root_dir / "data" / "processed" / "sc_censo_2022_populacao.json",
        root_dir / "sc_censo_2022_populacao.json",
    ]
    pop_file = next((p for p in pop_candidates if p.exists()), pop_candidates[0])
    with open(pop_file, "r", encoding="utf-8") as f:
        pop_map = json.load(f)

    client = IBGEClient()
    df_mun = client.get_municipios_df(uf="SC", engine="polars")

    code_to_meta: Dict[str, Dict[str, Any]] = {}
    name_to_code: Dict[str, str] = {}
    mun_list: List[Dict[str, Any]] = []
    sem_censo: List[str] = []

    for row in df_mun.to_dicts():
        cid = str(row["municipio-id"])
        pop = pop_map.get(cid)
        if pop is None:
            # Nao inventamos populacao: a ausencia e registrada na auditoria e a
            # taxa do municipio fica indefinida em vez de usar um valor plausivel.
            sem_censo.append(cid)
        meta = {
            "ibge_code": cid,
            "municipio_nome": row["municipio-nome"],
            "microrregiao": row["microrregiao-nome"],
            "regiao_imediata": row["regiao-imediata-nome"],
            "regiao_intermediaria": row["regiao-intermediaria-nome"],
            "populacao_censo_2022": int(pop) if pop is not None else None,
        }
        code_to_meta[cid] = meta
        name_to_code[normalizar_chave(row["municipio-nome"])] = cid
        mun_list.append(meta)

    pci_candidates = [
        root_dir / "data" / "processed" / "unidades_policia_cientifica_sc.json",
        root_dir / "unidades_policia_cientifica_sc.json",
    ]
    pci_file = next((p for p in pci_candidates if p.exists()), pci_candidates[0])
    pci_units: List[Dict[str, Any]] = []
    if pci_file.exists():
        with open(pci_file, "r", encoding="utf-8") as f:
            pci_units = json.load(f)

    return code_to_meta, name_to_code, mun_list, pci_units, sem_censo


def identificar_era(resolvedor: ResolvedorColunas, nome_arq: str) -> str:
    """Nomeia a era de esquema do arquivo, que determina o que pode ser medido."""
    col_id = resolvedor.coluna("id_denuncia")
    if col_id is None:
        return "2011 a 2019: arquivo anual, sem identificador de denúncia"
    if normalizar_chave(col_id) == "hash_par_vitima_suspeito":
        return "2020/1: identificador de par vítima-suspeito, não de denúncia"
    return "2020/2 a 2026: identificador de denúncia"


# =============================================================================
# 5. Pipeline principal
# =============================================================================

def processar_e_gerar_banco(root_dir: Path) -> None:
    t0 = time.time()
    code_to_meta, name_to_code, mun_list, pci_units, sem_censo = carregar_dados_auxiliares(root_dir)

    pqs = sorted(glob.glob(str(root_dir / "data" / "raw" / "disque100-*.parquet")))
    if not pqs:
        pqs = sorted(glob.glob(str(root_dir / "disque100-*.parquet")))
    print(f"Varrendo {len(pqs)} arquivos de microdados do Disque 100...")

    registros_fato: List[Dict[str, Any]] = []
    inventario: List[Dict[str, Any]] = []

    for p in pqs:
        nome_arq = os.path.basename(p)
        m_ano = re.search(r"20\d\d", nome_arq)
        ano = int(m_ano.group(0)) if m_ano else 0
        semestre = 1 if "primeiro-semestre" in nome_arq else (2 if "segundo-semestre" in nome_arq else 0)

        lazy = pl.scan_parquet(p)
        colunas = lazy.collect_schema().names()
        resolvedor = ResolvedorColunas(colunas)

        col_uf = resolvedor.coluna("uf")
        if col_uf is None:
            inventario.append({
                "arquivo": nome_arq, "ano": ano, "semestre": semestre,
                "erro": "coluna de UF não encontrada", "linhas_sc": 0,
            })
            print(f"  ! {nome_arq}: coluna de UF nao encontrada, arquivo ignorado.")
            continue

        df_sc = lazy.filter(
            pl.col(col_uf).cast(pl.Utf8).str.to_uppercase().str.strip_chars() == "SC"
        ).collect()
        n_sc = len(df_sc)

        col_id = resolvedor.coluna("id_denuncia")
        id_e_denuncia = col_id is not None and normalizar_chave(col_id) == "hash"

        item = {
            "arquivo": nome_arq,
            "ano": ano,
            "semestre": semestre,
            "era_esquema": identificar_era(resolvedor, nome_arq),
            "colunas_no_arquivo": len(colunas),
            "linhas_totais_arquivo": pl.scan_parquet(p).select(pl.len()).collect().item(),
            "linhas_sc": n_sc,
            "linhas_sc_distintas": int(df_sc.n_unique()) if n_sc else 0,
            "coluna_identificador": col_id,
            "identificador_e_denuncia": id_e_denuncia,
            "denuncias_sc_distintas": int(df_sc.select(pl.col(col_id).n_unique()).item()) if (col_id and n_sc) else None,
            "campos_resolvidos": sorted(resolvedor.mapa.keys()),
            "campos_ausentes": sorted(resolvedor.ausentes),
        }

        col_grupo = resolvedor.coluna("grupo_vulneravel")
        if col_grupo and n_sc:
            rotulos = (
                df_sc.select(pl.col(col_grupo).unique())
                .to_series()
                .drop_nulls()
                .to_list()
            )
            item["rotulos_modulo"] = sorted(str(r) for r in rotulos)
            item["modulos_declarados"] = modulos_declarados(rotulos)
        else:
            item["rotulos_modulo"] = []
            item["modulos_declarados"] = []
        if item["denuncias_sc_distintas"] and id_e_denuncia:
            item["fator_expansao_linhas_por_denuncia"] = round(n_sc / item["denuncias_sc_distintas"], 2)
        inventario.append(item)

        if n_sc == 0:
            print(f"  - {nome_arq}: nenhum registro de SC.")
            continue

        for idx, r in enumerate(df_sc.to_dicts()):
            c_penal = classificar_caso(r, resolvedor)
            c_grupo = classificar_grupos(r, resolvedor)

            cid = extrair_codigo_municipio(resolvedor.valor_bruto(r, "municipio"), name_to_code)
            meta_m = code_to_meta.get(cid) if cid else None

            id_den = r.get(col_id) if col_id else None
            id_den = str(id_den) if id_den not in (None, "") else None

            registros_fato.append({
                "id_fato": f"{ano}_{semestre}_{idx + 1}",
                "ano": ano,
                "semestre": semestre,
                "arquivo_origem": nome_arq,
                "id_denuncia": id_den,
                "grain_denuncia_confiavel": 1 if (id_e_denuncia and id_den) else 0,
                "ibge_code": cid or IBGE_NAO_IDENTIFICADO,
                "municipio_nome": meta_m["municipio_nome"] if meta_m else NOME_NAO_IDENTIFICADO,
                "regiao_intermediaria": meta_m["regiao_intermediaria"] if meta_m else "OUTRA",
                "regiao_imediata": meta_m["regiao_imediata"] if meta_m else "OUTRA",
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
                "is_prisional_rua": 1 if c_grupo["is_prisional_rua"] else 0,
            })

        print(f"  {nome_arq}: {n_sc:,} registros de SC classificados.")

    # Esquema explicito: `id_denuncia` e nulo em todos os arquivos de 2011-2019,
    # e a inferencia automatica do polars fixaria o tipo como Null antes de
    # encontrar o primeiro hash de 2020/2.
    df_fato = pl.DataFrame(registros_fato, schema=ESQUEMA_FATO)
    n_flags = sum(pl.col(f) for f in GRUPOS_CANONICOS)
    df_fato = df_fato.with_columns(
        (n_flags == 0).cast(pl.Int64).alias("sem_grupo"),
        n_flags.alias("qtd_grupos"),
    )
    print(f"\n{len(df_fato):,} registros consolidados em {time.time() - t0:.1f}s.")

    # -------------------------------------------------------------------------
    # 5.1 Fato e dimensoes em Parquet
    # -------------------------------------------------------------------------
    proc_dir = root_dir / "data" / "processed"
    proc_dir.mkdir(parents=True, exist_ok=True)

    fato_parquet = proc_dir / "sc_fato_denuncias.parquet"
    df_fato.write_parquet(fato_parquet, compression="zstd")
    print(f"Fato gravado: {fato_parquet.name} ({fato_parquet.stat().st_size / (1024 * 1024):.1f} MB)")

    df_dim_mun = pl.DataFrame(mun_list)
    df_dim_mun.write_parquet(proc_dir / "sc_dim_municipios.parquet", compression="zstd")

    df_dim_pci = construir_dim_pci(pci_units)
    df_dim_pci.write_parquet(proc_dir / "sc_dim_pci.parquet", compression="zstd")
    comp_pci = dict(df_dim_pci.group_by("tipo").len().iter_rows())
    print(f"Dimensao PCI-SC: {len(df_dim_pci)} unidades " + ", ".join(f"{v} {k}" for k, v in sorted(comp_pci.items())))

    # -------------------------------------------------------------------------
    # 5.2 KPIs por municipio, agregados em uma unica passada
    # -------------------------------------------------------------------------
    print("Agregando KPIs por municipio...")

    def soma(cond: pl.Expr, nome: str) -> pl.Expr:
        return cond.cast(pl.Int64).sum().alias(nome)

    penal = pl.col("indicio_penal") == 1
    confiavel = pl.col("grain_denuncia_confiavel") == 1

    aggs: List[pl.Expr] = [
        pl.len().alias("total_denuncias"),
        soma(penal, "total_penal"),
        pl.col("id_denuncia").filter(confiavel).n_unique().alias("denuncias_unicas"),
        # Denuncia com ao menos uma violacao tipificada. Nao e o mesmo que
        # denuncia predominantemente penal: uma denuncia com sete violacoes das
        # quais uma e tipificada entra aqui por inteiro, de modo que essa
        # proporcao fica muito acima da proporcao medida em violacoes.
        pl.col("id_denuncia").filter(confiavel & penal).n_unique().alias("denuncias_unicas_penal"),
        soma(pl.col("sem_grupo") == 1, "sem_grupo_total"),
        soma((pl.col("sem_grupo") == 1) & penal, "sem_grupo_penal"),
    ]
    for prefixo, flag in GRUPOS_KPI:
        marcado = pl.col(flag) == 1
        aggs.append(soma(marcado, f"{prefixo}_total"))
        aggs.append(soma(marcado & penal, f"{prefixo}_penal"))

    agg_mun = df_fato.group_by("ibge_code").agg(aggs)

    # Predominancia penal no nivel da denuncia: a maioria das violacoes daquela
    # denuncia e tipificada. E a medida comparavel a proporcao penal medida em
    # violacoes, e por isso acompanha a contagem de "ao menos um indicio".
    por_denuncia = (
        df_fato.filter(confiavel)
        .group_by(["ibge_code", "id_denuncia"])
        .agg(pl.len().alias("n"), pl.col("indicio_penal").sum().alias("p"))
        .with_columns((pl.col("p") * 2 > pl.col("n")).alias("maioria_penal"))
    )
    agg_predominancia = (
        por_denuncia.group_by("ibge_code")
        .agg(soma(pl.col("maioria_penal"), "denuncias_unicas_maioria_penal"))
    )
    agg_mun = agg_mun.join(agg_predominancia, on="ibge_code", how="left")

    df_kpis = (
        df_dim_mun.select(
            "ibge_code",
            pl.col("municipio_nome").alias("municipio"),
            "regiao_intermediaria",
            "regiao_imediata",
            "populacao_censo_2022",
        )
        .join(agg_mun, on="ibge_code", how="left")
        .fill_null(0)
    )

    pop = pl.col("populacao_censo_2022")
    # Taxa indefinida, e nao zero, quando a populacao do Censo esta ausente.
    def taxa(col: str, nome: str) -> pl.Expr:
        return (
            pl.when(pop > 0)
            .then((pl.col(col) / pop * 10000).round(2))
            .otherwise(None)
            .alias(nome)
        )

    colunas_taxa = [
        pl.col("total_denuncias").alias("total_registros"),
        (pl.col("total_denuncias") - pl.col("total_penal")).alias("total_social"),
        taxa("total_denuncias", "taxa_total_10k"),
        taxa("total_penal", "taxa_penal_10k"),
        taxa("denuncias_unicas", "taxa_denuncias_unicas_10k"),
        taxa("denuncias_unicas_maioria_penal", "taxa_denuncias_maioria_penal_10k"),
    ]
    for prefixo, _ in GRUPOS_KPI:
        colunas_taxa.append(taxa(f"{prefixo}_total", f"taxa_{prefixo}_10k"))
        colunas_taxa.append(taxa(f"{prefixo}_penal", f"taxa_{prefixo}_penal_10k"))
    df_kpis = df_kpis.with_columns(colunas_taxa)

    kpis_parquet = proc_dir / "sc_kpis_grupos_municipios.parquet"
    df_kpis.write_parquet(kpis_parquet, compression="zstd")
    df_kpis.write_csv(proc_dir / "sc_kpis_grupos_municipios.csv")
    print(f"KPIs municipais gravados: {kpis_parquet.name} ({len(df_kpis)} municipios)")

    # -------------------------------------------------------------------------
    # 5.3 KPIs por categoria penal
    # -------------------------------------------------------------------------
    df_cat = (
        df_fato.group_by([
            "ano", "semestre", "regiao_intermediaria", "categoria_penal",
            "grau_certeza", "orgao_prioritario", "fundamentacao_legal", "indicio_penal",
        ])
        .agg(
            pl.len().alias("registros"),
            pl.col("id_denuncia").filter(confiavel).n_unique().alias("denuncias_unicas"),
        )
        .sort(["ano", "semestre", "registros"], descending=[False, False, True])
    )
    cat_parquet = proc_dir / "sc_kpis_categoria_penal.parquet"
    df_cat.write_parquet(cat_parquet, compression="zstd")
    print(f"KPIs por categoria penal gravados: {cat_parquet.name} ({len(df_cat)} combinacoes)")

    # -------------------------------------------------------------------------
    # 5.4 Cargas SQLite e DuckDB
    # -------------------------------------------------------------------------
    db_dir = root_dir / "data" / "database"
    db_dir.mkdir(parents=True, exist_ok=True)
    sqlite_path = db_dir / "sc_disque100_analitico.sqlite"
    conn = sqlite3.connect(sqlite_path)
    df_dim_mun.to_pandas().to_sql("dim_municipios", conn, if_exists="replace", index=False)
    df_dim_pci.to_pandas().to_sql("dim_unidades_pci", conn, if_exists="replace", index=False)
    df_kpis.to_pandas().to_sql("kpis_grupos_municipios", conn, if_exists="replace", index=False)
    df_cat.to_pandas().to_sql("kpis_categoria_penal", conn, if_exists="replace", index=False)
    cur = conn.cursor()
    cur.execute("CREATE INDEX IF NOT EXISTS idx_kpi_ibge ON kpis_grupos_municipios(ibge_code);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_kpi_regiao ON kpis_grupos_municipios(regiao_intermediaria);")
    conn.commit()
    conn.close()
    print(f"SQLite carregado e indexado: {sqlite_path.name}")

    try:
        import duckdb

        duck_out = db_dir / "sc_disque100_analitico.duckdb"
        for _ in (1,):
            dcon = duckdb.connect(str(duck_out))
            dcon.register("v_dim_mun", df_dim_mun.to_arrow())
            dcon.register("v_dim_pci", df_dim_pci.to_arrow())
            dcon.register("v_kpis", df_kpis.to_arrow())
            dcon.register("v_cat", df_cat.to_arrow())
            dcon.register("v_fato", df_fato.to_arrow())
            dcon.execute("CREATE OR REPLACE TABLE dim_municipios AS SELECT * FROM v_dim_mun")
            dcon.execute("CREATE OR REPLACE TABLE dim_unidades_pci AS SELECT * FROM v_dim_pci")
            dcon.execute("CREATE OR REPLACE TABLE kpis_grupos_municipios AS SELECT * FROM v_kpis")
            dcon.execute("CREATE OR REPLACE TABLE kpis_categoria_penal AS SELECT * FROM v_cat")
            dcon.execute("CREATE OR REPLACE TABLE fato_denuncias AS SELECT * FROM v_fato")
            dcon.close()
        print(f"DuckDB gravado: {duck_out.relative_to(root_dir)}")
    except Exception as err:
        print(f"Aviso DuckDB: {err}")

    # -------------------------------------------------------------------------
    # 5.5 Relatorio de auditoria
    # -------------------------------------------------------------------------
    relatorio = montar_relatorio_auditoria(root_dir, df_fato, df_kpis, df_dim_pci, inventario, sem_censo)
    audit_file = proc_dir / "sc_relatorio_auditoria_dados.json"
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)

    # Os hashes sao fechados pelo ultimo passo do pipeline
    # (`analisar_distribuicao_penal_sc.py`), quando todos os artefatos de
    # data/processed/ ja existem na versao final.
    relatorio["arquivos_hashes_sha256"] = hashes_processados(proc_dir)
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)

    imprimir_resumo(relatorio)


# =============================================================================
# 6. Auditoria
# =============================================================================

def hashes_processados(proc_dir: Path) -> Dict[str, str]:
    """SHA-256 de cada artefato publicado em data/processed/."""
    saida: Dict[str, str] = {}
    for nome in sorted(os.listdir(proc_dir)):
        caminho = proc_dir / nome
        if caminho.is_file() and nome != "sc_relatorio_auditoria_dados.json":
            with open(caminho, "rb") as f:
                saida[nome] = hashlib.sha256(f.read()).hexdigest()
    return saida


def montar_relatorio_auditoria(
    root_dir: Path,
    df_fato: pl.DataFrame,
    df_kpis: pl.DataFrame,
    df_dim_pci: pl.DataFrame,
    inventario: List[Dict[str, Any]],
    sem_censo: List[str],
) -> Dict[str, Any]:
    """
    Monta o relatorio que sustenta as afirmacoes do painel.

    A versao anterior registrava apenas os totais que ela mesma havia produzido
    e declarava "APROVADO" com base na identidade total = penal + social, que
    nao pode falhar porque social e definido como total menos penal. Aqui o
    relatorio traz o que de fato permite julgar os numeros: inventario por
    arquivo, cobertura de cada indicador por semestre, fator de expansao entre
    registro e denuncia, anos incompletos, comparacao com o balanco oficial do
    MDHC e as limitacoes conhecidas.
    """
    total = len(df_fato)
    penal = int(df_fato.select(pl.col("indicio_penal").sum()).item())
    confiavel = pl.col("grain_denuncia_confiavel") == 1

    por_semestre = (
        df_fato.group_by(["ano", "semestre"])
        .agg(
            pl.len().alias("registros"),
            pl.col("indicio_penal").sum().alias("penal"),
            pl.col("id_denuncia").filter(confiavel).n_unique().alias("denuncias_unicas"),
            *[pl.col(f).sum().alias(f) for f in GRUPOS_CANONICOS],
            pl.col("sem_grupo").sum().alias("sem_grupo"),
            (pl.col("ibge_code") == IBGE_NAO_IDENTIFICADO).cast(pl.Int64).sum().alias("municipio_nao_identificado"),
        )
        .sort(["ano", "semestre"])
    )
    cobertura: List[Dict[str, Any]] = []
    for row in por_semestre.iter_rows(named=True):
        item = dict(row)
        reg = item["registros"] or 1
        item["pct_penal"] = round(100.0 * item["penal"] / reg, 2)
        item["pct_sem_grupo"] = round(100.0 * item["sem_grupo"] / reg, 2)
        item["fator_expansao"] = (
            round(item["registros"] / item["denuncias_unicas"], 2) if item["denuncias_unicas"] else None
        )
        cobertura.append(item)

    anos = df_fato.select(pl.col("ano").unique().sort()).to_series().to_list()
    semestres_por_ano = {
        str(a): sorted(
            df_fato.filter(pl.col("ano") == a).select(pl.col("semestre").unique()).to_series().to_list()
        )
        for a in anos
    }
    anos_incompletos = {
        a: s for a, s in semestres_por_ano.items() if s != [0] and len(s) < 2
    }

    # Expansao por municipio: e a dispersao desse fator, e nao a media, que
    # inviabiliza comparar municipios por contagem de linha.
    exp_mun = (
        df_fato.filter(confiavel)
        .group_by("ibge_code")
        .agg(pl.len().alias("registros"), pl.col("id_denuncia").n_unique().alias("denuncias"))
        .filter(pl.col("denuncias") >= 30)
        .with_columns((pl.col("registros") / pl.col("denuncias")).round(2).alias("fator"))
    )
    dispersao = {}
    if len(exp_mun):
        s = exp_mun.select("fator").to_series()
        dispersao = {
            "municipios_considerados": len(exp_mun),
            "criterio": "municípios com ao menos 30 denúncias identificáveis",
            "fator_minimo": float(s.min()),
            "fator_mediano": float(s.median()),
            "fator_maximo": float(s.max()),
        }

    pop_total = df_kpis.select(pl.col("populacao_censo_2022").sum()).item()
    total_municipalizado = int(df_kpis.select(pl.col("total_denuncias").sum()).item())

    return {
        "timestamp_auditoria": time.strftime("%Y-%m-%d %H:%M:%S"),
        "unidade_de_medida": {
            "registro_de_violacao": (
                "Uma linha dos microdados: combinação de violação, vítima e suspeito. "
                "É a unidade das contagens históricas de 2011 a 2026."
            ),
            "denuncia_unica": (
                "Contagem distinta do identificador oficial da denúncia, disponível a partir "
                "de 2020/2. É a unidade comparável com os balanços publicados pelo MDHC."
            ),
            "advertencia": (
                "Contagens de registro de violação não são comparáveis entre anos nem entre "
                "municípios, porque o fator de expansão entre denúncia e registro varia em "
                "ambas as dimensões."
            ),
        },
        "totais": {
            "registros_de_violacao": total,
            "registros_penal": penal,
            "registros_social": total - penal,
            "pct_penal": round(100.0 * penal / max(total, 1), 2),
            "denuncias_unicas_identificaveis": int(
                df_fato.select(pl.col("id_denuncia").filter(confiavel).n_unique()).item()
            ),
            "registros_com_denuncia_identificavel": int(
                df_fato.select(pl.col("grain_denuncia_confiavel").sum()).item()
            ),
            "periodo": f"{min(anos)} a {max(anos)}" if anos else "indisponivel",
        },
        "conciliacao_municipal": {
            "registros_no_fato": total,
            "registros_atribuidos_a_municipio": total_municipalizado,
            "registros_sem_municipio_identificado": total - total_municipalizado,
            "observacao": (
                "A diferença corresponde aos registros com código sentinela "
                f"{IBGE_NAO_IDENTIFICADO}, excluídos dos indicadores municipais porque não há "
                "município a que atribuí-los. O painel diz explicitamente qual das duas bases "
                "está em uso."
            ),
        },
        "grupos_vulneraveis": {
            "totais": {f: int(df_fato.select(pl.col(f).sum()).item()) for f in GRUPOS_CANONICOS},
            "sem_grupo_identificado": int(df_fato.select(pl.col("sem_grupo").sum()).item()),
            "registros_em_mais_de_um_grupo": int(
                df_fato.select((pl.col("qtd_grupos") >= 2).cast(pl.Int64).sum()).item()
            ),
            "advertencia": (
                "As marcações não são mutuamente exclusivas e não somam o total: um mesmo "
                "registro pode pertencer a vários grupos, e parte não pertence a nenhum. "
                "Não devem ser apresentadas como partição nem em gráfico de pizza."
            ),
        },
        "demografia": {
            "fonte": "IBGE, Censo Demográfico 2022, tabela SIDRA 4714, variável 93",
            "municipios": len(df_kpis),
            "populacao_total": int(pop_total) if pop_total is not None else None,
            "municipios_sem_populacao_no_censo": sem_censo,
            "limitacao_denominador": (
                "O denominador é um estoque populacional de um único ano, o Censo 2022. "
                "Para os anos mais distantes de 2022 é apenas uma aproximação, e as taxas não "
                "se comparam diretamente a indicadores criminais publicados."
            ),
        },
        "policia_cientifica": {
            "fonte": "Polícia Científica de Santa Catarina, portal de unidades",
            "total_unidades": len(df_dim_pci),
            "composicao": dict(sorted(df_dim_pci.group_by("tipo").len().iter_rows())),
            "unidades_com_coordenada": int(
                df_dim_pci.select(((pl.col("lat") != 0) & (pl.col("lon") != 0)).cast(pl.Int64).sum()).item()
            ),
            "limitacao_distancia": (
                "As distâncias entre município e unidade são geodésicas, medidas em linha "
                "reta por haversine. Não são distâncias rodoviárias e não sustentam, por si, "
                "estimativa de tempo de deslocamento."
            ),
        },
        "comparabilidade_grupos": comparabilidade_grupos(inventario),
        "cobertura_por_semestre": cobertura,
        "anos_incompletos": anos_incompletos,
        "dispersao_fator_expansao_municipal": dispersao,
        "inventario_arquivos": inventario,
        "validacao_externa_mdhc": ler_balanco_oficial_mdh(root_dir),
        "limitacoes_conhecidas": [
            "A classificação penal é automatizada por taxonomia de palavras-chave sobre o "
            "texto da violação relatada. Não é decisão jurídica, não foi validada contra "
            "laudo ou inquérito, e sua precisão não foi medida.",
            "O percentual penal não é comparável ao longo da série: o vocabulário de violação "
            "muda entre as eras de esquema, e com ele a fração do texto que a taxonomia "
            "reconhece.",
            "O arquivo de 2023/1 não traz a coluna de grupo vulnerável. Nesse semestre a "
            "atribuição de grupo depende apenas de faixa etária, deficiência e orientação "
            "sexual, e a proporção sem grupo identificado é estruturalmente maior.",
            "O município registrado é o da denúncia, não necessariamente o de residência da "
            "vítima nem o da ocorrência.",
            "No nível da denúncia, ter indício penal significa ter ao menos uma violação "
            "tipificada. Uma denúncia com sete violações das quais uma é penal entra por "
            "inteiro nessa contagem, que por isso fica bem acima da proporção medida em "
            "registros de violação; a medida comparável é a predominância penal.",
            "Denúncia registrada não equivale a violação confirmada. A base mede demanda "
            "notificada e é sensível à subnotificação, que varia por território e por grupo.",
        ],
    }


def comparabilidade_grupos(inventario: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Declara, para cada grupo vulneravel, os anos em que o modulo correspondente
    existia nos microdados.

    Sem isso, o painel apresentaria como crescimento o que e apenas a criacao de
    um modulo: o de "Violencia contra a Mulher" nao existe nos microdados antes
    de 2025, e a serie desse grupo depende, nos anos anteriores, apenas de
    inferencia a partir de genero e relacao vitima-suspeito.
    """
    anos_por_grupo: Dict[str, set] = {}
    anos_com_coluna: set = set()
    anos_sem_coluna: set = set()

    for item in inventario:
        ano = item.get("ano")
        if not ano or not item.get("linhas_sc"):
            continue
        if "grupo_vulneravel" in (item.get("campos_ausentes") or []):
            anos_sem_coluna.add(ano)
            continue
        anos_com_coluna.add(ano)
        for grupo in item.get("modulos_declarados") or []:
            anos_por_grupo.setdefault(grupo, set()).add(ano)

    saida: Dict[str, Any] = {}
    for grupo in GRUPOS_CANONICOS:
        anos = sorted(anos_por_grupo.get(grupo, set()))
        saida[grupo] = {
            "anos_com_modulo_proprio": anos,
            "primeiro_ano_com_modulo": anos[0] if anos else None,
            "comparavel_desde": anos[0] if anos else None,
            "observacao": (
                "Módulo próprio ausente em toda a série; a marcação depende de inferência."
                if not anos else
                f"Antes de {anos[0]}, a marcação depende de inferência, e não do módulo declarado."
                if anos[0] > 2011 else
                "Módulo presente em toda a série coberta."
            ),
        }

    return {
        "criterio": (
            "Um grupo é considerado comparável no período em que o próprio Disque 100 "
            "mantém um módulo daquele público no campo de grupo vulnerável."
        ),
        "anos_sem_coluna_de_grupo": sorted(anos_sem_coluna),
        "por_grupo": saida,
    }


def imprimir_resumo(relatorio: Dict[str, Any]) -> None:
    t = relatorio["totais"]
    print("=" * 72)
    print(f"Periodo                              {t['periodo']}")
    print(f"Registros de violacao                {t['registros_de_violacao']:>12,}")
    print(f"  com indicio penal                  {t['registros_penal']:>12,} ({t['pct_penal']:.2f}%)")
    print(f"  demanda socioassistencial          {t['registros_social']:>12,}")
    print(f"Denuncias unicas identificaveis      {t['denuncias_unicas_identificaveis']:>12,}")
    g = relatorio["grupos_vulneraveis"]
    print("Grupos vulneraveis (nao exclusivos):")
    for nome, val in g["totais"].items():
        print(f"  {nome:<20s} {val:>12,}")
    print(f"  {'sem grupo':<20s} {g['sem_grupo_identificado']:>12,}")
    ext = relatorio["validacao_externa_mdhc"]
    if ext.get("disponivel"):
        print(f"Balanco oficial MDHC 2011-2019       {ext['total_denuncias_sc']:>12,} denuncias")
    if relatorio["anos_incompletos"]:
        print(f"Anos incompletos                     {relatorio['anos_incompletos']}")
    print("=" * 72)


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    if base.name == "scripts":
        base = base.parent
    processar_e_gerar_banco(base)
