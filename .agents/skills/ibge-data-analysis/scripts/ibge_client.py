"""
=============================================================================
IBGE Data Analysis & Geospatial Client - Full-Featured Python Helper
=============================================================================
Cliente universal para consumo otimizado, cacheado e integrado com Pandas,
Polars, GeoPandas, Plotly e Folium das APIs de Localidades e Malhas do IBGE.
=============================================================================
"""

import os
import json
import requests
from pathlib import Path
from typing import Optional, Union, Dict, Any, List

class IBGEClient:
    """
    Cliente utilitário avançado para as APIs de Localidades e Malhas do IBGE.
    Suporta cache em disco, múltiplas engines de DataFrame (Pandas/Polars/GeoPandas)
    e todas as escalas territoriais do Brasil.
    """
    
    BASE_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades"
    BASE_MALHAS = "https://servicodados.ibge.gov.br/api/v4/malhas"
    CACHE_DIR = Path.home() / ".cache" / "ibge_data"

    # Mapeamento Sigla -> Código IBGE das 27 UFs
    UF_SIGLA_TO_ID = {
        "RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17,
        "MA": 21, "PI": 22, "CE": 23, "RN": 24, "PB": 25, "PE": 26, "AL": 27, "SE": 28, "BA": 29,
        "MG": 31, "ES": 32, "RJ": 33, "SP": 35,
        "PR": 41, "SC": 42, "RS": 43,
        "MS": 50, "MT": 51, "GO": 52, "DF": 53
    }

    def __init__(self, cache_dir: Optional[Union[str, Path]] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else self.CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Python/IBGE-Data-Client; Data-Science-Polars-Pandas)"
        })

    def _normalize_uf(self, uf: Union[int, str]) -> str:
        """Converte sigla (ex: 'SP') para código IBGE (ex: '35') ou valida código."""
        uf_str = str(uf).strip().upper()
        if uf_str in self.UF_SIGLA_TO_ID:
            return str(self.UF_SIGLA_TO_ID[uf_str])
        return uf_str

    def _rewind_for_d3(self, geojson: Dict[str, Any]) -> Dict[str, Any]:
        """Corrige a ordem dos vértices dos polígonos (Right-Hand Rule) para compatibilidade perfeita com D3.js e Plotly."""
        g = json.loads(json.dumps(geojson))
        for feat in g.get("features", []):
            geom = feat.get("geometry", {})
            t = geom.get("type")
            coords = geom.get("coordinates", [])
            if t == "Polygon":
                geom["coordinates"] = [ring[::-1] for ring in coords]
            elif t == "MultiPolygon":
                geom["coordinates"] = [[ring[::-1] for ring in poly] for poly in coords]
        return g

    # =========================================================================
    # 1. API DE LOCALIDADES (TABULAR & METADADOS)
    # =========================================================================

    def get_municipios(
        self,
        uf: Optional[Union[int, str, List[Union[int, str]]]] = None,
        view: str = "nivelado",
        use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retorna a lista de municípios do Brasil ou de UFs específicas.
        - Se uf for especificado (ex: 'SP', 35 ou ['SP', 'RJ']): filtra os municípios daquelas UFs.
        - Quando view='nivelado': retorna JSON plano ideal para DataFrames.
        """
        if uf:
            if isinstance(uf, list):
                uf_codes = "|".join(self._normalize_uf(u) for u in uf)
            else:
                uf_codes = self._normalize_uf(uf)
            endpoint = f"estados/{uf_codes}/municipios"
            cache_name = f"municipios_uf_{uf_codes}_{view}.json"
        else:
            endpoint = "municipios"
            cache_name = f"municipios_todos_{view}.json"

        cache_file = self.cache_dir / cache_name
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        url = f"{self.BASE_LOCALIDADES}/{endpoint}"
        params = {"view": view, "orderBy": "nome"} if view else {"orderBy": "nome"}
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        return data

    def get_municipios_df(
        self,
        uf: Optional[Union[int, str, List[Union[int, str]]]] = None,
        engine: str = "polars"
    ) -> Any:
        """Retorna os municípios como DataFrame do Polars (padrão) ou Pandas."""
        data = self.get_municipios(uf=uf, view="nivelado")
        if engine.lower() == "polars":
            import polars as pl
            return pl.DataFrame(data)
        elif engine.lower() == "pandas":
            import pandas as pd
            return pd.DataFrame(data)
        return data

    def get_estados(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Retorna todas as 27 Unidades da Federação (UFs)."""
        cache_file = self.cache_dir / "estados.json"
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        url = f"{self.BASE_LOCALIDADES}/estados"
        resp = self.session.get(url, params={"orderBy": "nome"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        return data

    def get_estados_df(self, engine: str = "polars") -> Any:
        """Retorna as 27 UFs como DataFrame do Polars ou Pandas."""
        data = self.get_estados()
        # Normaliza estrutura
        flat = []
        for d in data:
            flat.append({
                "uf_id": d["id"],
                "uf_sigla": d["sigla"],
                "uf_nome": d["nome"],
                "regiao_id": d["regiao"]["id"],
                "regiao_sigla": d["regiao"]["sigla"],
                "regiao_nome": d["regiao"]["nome"],
            })
        if engine.lower() == "polars":
            import polars as pl
            return pl.DataFrame(flat)
        elif engine.lower() == "pandas":
            import pandas as pd
            return pd.DataFrame(flat)
        return flat

    def get_regioes(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """Retorna as 5 Macrorregiões do Brasil."""
        cache_file = self.cache_dir / "regioes.json"
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        url = f"{self.BASE_LOCALIDADES}/regioes"
        resp = self.session.get(url, params={"orderBy": "nome"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        return data

    def get_regioes_intermediarias(self, view: str = "nivelado", use_cache: bool = True) -> List[Dict[str, Any]]:
        """Retorna as 133 Regiões Geográficas Intermediárias do Brasil."""
        url = f"{self.BASE_LOCALIDADES}/regioes-intermediarias"
        params = {"view": view, "orderBy": "nome"} if view else {"orderBy": "nome"}
        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def get_regioes_imediatas(self, view: str = "nivelado", use_cache: bool = True) -> List[Dict[str, Any]]:
        """Retorna as 510 Regiões Geográficas Imediatas do Brasil."""
        url = f"{self.BASE_LOCALIDADES}/regioes-imediatas"
        params = {"view": view, "orderBy": "nome"} if view else {"orderBy": "nome"}
        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    def get_distritos(self, view: str = "nivelado", use_cache: bool = True) -> List[Dict[str, Any]]:
        """Retorna os distritos do Brasil."""
        url = f"{self.BASE_LOCALIDADES}/distritos"
        params = {"view": view, "orderBy": "nome"} if view else {"orderBy": "nome"}
        resp = self.session.get(url, params=params, timeout=40)
        resp.raise_for_status()
        return resp.json()

    # =========================================================================
    # 2. API DE MALHAS GEOGRÁFICAS v4 (ESPACIAL / GEOJSON / VETORES)
    # =========================================================================

    def get_malha_paises_geojson(
        self,
        intrarregiao: str = "UF",
        qualidade: str = "minima",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Retorna GeoJSON do Brasil subdividido por intrarregiao:
        - intrarregiao='regiao' (5 features)
        - intrarregiao='UF' (27 features - padrão)
        - intrarregiao='regiao-intermediaria' (133 features)
        - intrarregiao='regiao-imediata' (510 features)
        - intrarregiao='municipio' (5.571 features)
        """
        cache_file = self.cache_dir / f"malha_BR_{intrarregiao}_{qualidade}.geojson"
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        url = f"{self.BASE_MALHAS}/paises/BR"
        params = {
            "formato": "application/vnd.geo+json",
            "intrarregiao": intrarregiao,
            "qualidade": qualidade
        }
        resp = self.session.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        # Garante feature['id'] e ordem de anéis (Right-Hand Rule) para compatibilidade com Plotly/D3/Folium
        data = self._rewind_for_d3(data)
        if "features" in data:
            for f in data["features"]:
                if "properties" in f and "codarea" in f["properties"]:
                    f["id"] = str(f["properties"]["codarea"])

        return data

    def get_malha_estados_geojson(self, qualidade: str = "minima", use_cache: bool = True) -> Dict[str, Any]:
        """Retorna o GeoJSON das 27 UFs do Brasil."""
        return self.get_malha_paises_geojson(intrarregiao="UF", qualidade=qualidade, use_cache=use_cache)

    def get_malha_municipios_uf_geojson(
        self,
        uf: Union[int, str],
        intrarregiao: str = "municipio",
        qualidade: str = "minima",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Retorna o GeoJSON dos municípios de uma UF específica (ex: 'SP', 35, 'RJ', 33).
        - intrarregiao pode ser: 'municipio', 'regiao-imediata', 'regiao-intermediaria'.
        """
        uf_id = self._normalize_uf(uf)
        cache_file = self.cache_dir / f"malha_uf_{uf_id}_{intrarregiao}_{qualidade}.geojson"
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)
                return self._rewind_for_d3(cached_data)

        url = f"{self.BASE_MALHAS}/estados/{uf_id}"
        params = {
            "formato": "application/vnd.geo+json",
            "intrarregiao": intrarregiao,
            "qualidade": qualidade
        }
        resp = self.session.get(url, params=params, timeout=45)
        resp.raise_for_status()
        data = resp.json()

        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        data = self._rewind_for_d3(data)
        if "features" in data:
            for f in data["features"]:
                if "properties" in f and "codarea" in f["properties"]:
                    f["id"] = str(f["properties"]["codarea"])

        return data

    def get_malha_municipio_geojson(
        self,
        municipio_id: Union[int, str],
        qualidade: str = "intermediaria",
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Retorna o contorno vetorial individual de um único município pelo código de 7 dígitos."""
        cache_file = self.cache_dir / f"malha_mun_{municipio_id}_{qualidade}.geojson"
        if use_cache and cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

        url = f"{self.BASE_MALHAS}/municipios/{municipio_id}"
        params = {
            "formato": "application/vnd.geo+json",
            "qualidade": qualidade
        }
        resp = self.session.get(url, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if use_cache:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)

        return data

    def get_malha_gdf(
        self,
        scope: str = "estados",
        uf: Optional[Union[int, str]] = None,
        qualidade: str = "minima"
    ) -> Any:
        """
        Retorna diretamente um GeoDataFrame do GeoPandas pronto para análise e mapas.
        - scope='estados': Todas as UFs do Brasil.
        - scope='municipios_uf': Todos os municípios de uma UF específica (requer parâmetro uf='SP').
        - scope='regioes': As 5 macrorregiões do Brasil.
        """
        import geopandas as gpd

        if scope == "estados":
            geojson = self.get_malha_estados_geojson(qualidade=qualidade)
        elif scope == "municipios_uf":
            if not uf:
                raise ValueError("Parâmetro 'uf' é obrigatório para scope='municipios_uf'")
            geojson = self.get_malha_municipios_uf_geojson(uf=uf, intrarregiao="municipio", qualidade=qualidade)
        elif scope == "regioes":
            geojson = self.get_malha_paises_geojson(intrarregiao="regiao", qualidade=qualidade)
        else:
            raise ValueError(f"Scope '{scope}' não suportado.")

        return gpd.GeoDataFrame.from_features(geojson["features"], crs="EPSG:4674")  # SIRGAS 2000
