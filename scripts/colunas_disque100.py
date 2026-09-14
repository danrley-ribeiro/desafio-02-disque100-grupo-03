#!/usr/bin/env python3
"""
=============================================================================
Resolvedor de Colunas dos Microdados do Disque 100 (2011-2026)
=============================================================================
Os 22 arquivos publicados pelo MDHC nao usam um esquema estavel. A mesma
informacao aparece com grafias diferentes entre anos e semestres, e alguns
arquivos simplesmente nao trazem certas colunas. Grafias reais observadas:

  genero da vitima ..... vitima_sexo            (2011-2019)
                         Genero da vitima       (2020/2 a 2022/1, com espacos)
                         Genero_da_vitima       (2023, 2026)
                         Sexo_da_vitima         (somente 2024/2)
                         Genero_da_vitima       (2025/1, sem acento em "Genero")
  grupo vulneravel ..... grupo_violacao / Grupo vulneravel / Grupo_vulneravel
                         AUSENTE em disque100-primeiro-semestre-2023.parquet
  faixa etaria ......... vitima_faixa_etaria / Faixa etaria da vitima /
                         Faixa_etaria_da_vitima / idade_vitima (2020/1)
  deficiencia .......... Deficiencia da vitima / Deficiencia_da_vitima /
                         deficiencia_vitima (2020/1)

Resolver essas grafias com `row.get("A") or row.get("B")` deixou de fora
metade da serie e zerou indicadores inteiros. Este modulo normaliza as chaves
(minusculas, sem acento, sem pontuacao, separadores colapsados) e resolve cada
campo canonico por uma lista de aliases, registrando o que nao foi encontrado
para que a lacuna apareca no relatorio de auditoria em vez de virar silencio.
=============================================================================
"""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "ALIASES_CANONICOS",
    "NULOS_EXATOS",
    "NULOS_PREFIXOS",
    "NULOS_TEXTUAIS",
    "normalizar_chave",
    "ResolvedorColunas",
    "texto_limpo",
]


# Valores que representam ausencia de informacao e nunca devem ser tratados
# como conteudo. A lista foi levantada varrendo os 22 arquivos: sem ela,
# "N/D" (48.384 ocorrencias no campo de deficiencia) e "NAO TEM DEFICIENCIA"
# (11.274) seriam lidos como deficiencia declarada.
#
# As chaves estao na forma normalizada por `normalizar_chave`, para que acento,
# caixa, barra e pontuacao nao precisem ser enumerados.
NULOS_EXATOS = frozenset({
    "", "nan", "null", "none", "na", "n_a", "n_d", "nd", "ni",
    "nao", "sim_nao", "vazio", "ignorado", "indefinido",
    "nao_tem_deficiencia", "sem_deficiencia", "nao_possui",
    "sem_informacao", "atendimento_interrompido",
})

# Prefixos normalizados: cobrem as variantes longas, como
# "NAO SE APLICA - VITIMA COMUNIDADE/FAMILIA" (5.058 ocorrencias no campo de
# genero) e "DENUNCIANTE NAO SOUBE INFORMAR" (campo de municipio).
NULOS_PREFIXOS = (
    "nao_informad", "nao_identificad", "nao_declarad", "nao_soube",
    "nao_se_aplica", "denunciante_nao_soube", "sem_informac",
)

# Mantido pelo nome antigo para nao quebrar importacoes externas.
NULOS_TEXTUAIS = NULOS_EXATOS


# Campo canonico -> grafias aceitas. As grafias sao comparadas apos
# normalizacao, portanto acento, caixa, espaco duplo e underscore sao
# equivalentes: basta listar uma variante de cada forma realmente distinta.
ALIASES_CANONICOS: Dict[str, List[str]] = {
    # Identificacao e localizacao
    "id_denuncia": ["hash", "hash_par_vitima_suspeito"],
    "uf": ["UF", "vitima_uf", "UF da vítima", "Estado"],
    "municipio": [
        "vitima_cod_municipio", "Município", "Município da vítima",
        "vitima_municipio", "sl_vitima_naturalizado_municipio",
    ],
    "data_cadastro": ["Data de cadastro", "Data da denúncia", "data_atendimento"],

    # Perfil da vitima
    "grupo_vulneravel": ["Grupo vulnerável", "grupo_violacao"],
    "subgrupo_violacao": ["sub_grupo_violacao"],
    "genero_vitima": [
        "Gênero da vítima", "Genero da vítima", "Sexo da vítima", "vitima_sexo",
    ],
    "faixa_etaria_vitima": [
        "Faixa etária da vítima", "vitima_faixa_etaria", "idade_vitima",
    ],
    "deficiencia_vitima": ["Deficiência da vítima", "deficiencia_vitima"],
    "orientacao_sexual_vitima": [
        "Orientação sexual da vítima", "vitima_orientacao_sexual", "orientacao_sexual",
    ],
    "vitima_presa": ["Vítima preso(a)", "Vítima preso a"],

    # Violacao e contexto
    "violacao": ["violacao", "violacoes"],
    "motivacao": ["Motivação", "motivacoes", "relacao_suspeito"],
    "relacao_vitima_suspeito": [
        "Relação vítima-suspeito", "Relação Suspeito x Vítima", "relacao_suspeito",
    ],
    "cenario_violacao": ["Cenário da violação", "cenario_local", "cenario_ocorrencia"],
    "denuncia_emergencial": ["Denúncia emergencial", "Denúncia Emergencial"],
    "suspeito_preso": ["Suspeito preso"],
}


def normalizar_chave(nome: Any) -> str:
    """
    Reduz um nome de coluna a uma forma comparavel: sem acento, minusculo,
    com qualquer sequencia de caracteres nao alfanumericos colapsada em "_".

    >>> normalizar_chave("Gênero_da_vítima")
    'genero_da_vitima'
    >>> normalizar_chave("Município  da vítima")
    'municipio_da_vitima'
    >>> normalizar_chave("Deficiência relacionada a doença rara ?")
    'deficiencia_relacionada_a_doenca_rara'
    """
    if nome is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(nome))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    saida: List[str] = []
    for ch in texto.lower():
        saida.append(ch if ch.isalnum() else "_")
    return "_".join(p for p in "".join(saida).split("_") if p)


def texto_limpo(valor: Any) -> str:
    """
    Devolve o valor em maiuscula e sem espacos nas pontas, ou "" quando o
    conteudo representa ausencia de informacao. Centraliza o tratamento de
    nulos textuais para que nenhum classificador precise repeti-lo.
    """
    if valor is None:
        return ""
    try:
        # Cobre float('nan') de pandas/polars sem depender das bibliotecas.
        if valor != valor:  # noqa: PLR0124 - teste de NaN
            return ""
    except Exception:
        pass
    s = str(valor).strip()
    if not s:
        return ""
    chave = normalizar_chave(s)
    if chave in NULOS_EXATOS or any(chave.startswith(pref) for pref in NULOS_PREFIXOS):
        return ""
    return s.upper()


class ResolvedorColunas:
    """
    Mapeia campos canonicos para os nomes reais de coluna de um arquivo.

    A resolucao acontece uma vez por arquivo, a partir da lista de colunas do
    esquema, e nao a cada linha. Depois disso `valor(row, "genero_vitima")` e
    um acesso direto de dicionario.
    """

    def __init__(self, colunas: Iterable[str], aliases: Optional[Dict[str, List[str]]] = None):
        self.aliases = aliases or ALIASES_CANONICOS
        self.colunas_originais = list(colunas)
        # normalizado -> nome original, preservando a primeira ocorrencia
        indice: Dict[str, str] = {}
        for c in self.colunas_originais:
            chave = normalizar_chave(c)
            indice.setdefault(chave, c)
        self._indice = indice

        self.mapa: Dict[str, str] = {}
        self.ausentes: List[str] = []
        for canonico, variantes in self.aliases.items():
            achado = None
            for v in variantes:
                real = indice.get(normalizar_chave(v))
                if real is not None:
                    achado = real
                    break
            if achado is not None:
                self.mapa[canonico] = achado
            else:
                self.ausentes.append(canonico)

    def coluna(self, canonico: str) -> Optional[str]:
        """Nome real da coluna para um campo canonico, ou None se ausente."""
        return self.mapa.get(canonico)

    def tem(self, canonico: str) -> bool:
        return canonico in self.mapa

    def valor(self, row: Dict[str, Any], canonico: str) -> str:
        """Valor textual limpo do campo canonico nesta linha."""
        col = self.mapa.get(canonico)
        if col is None:
            return ""
        return texto_limpo(row.get(col))

    def valor_bruto(self, row: Dict[str, Any], canonico: str) -> Any:
        """Valor sem tratamento, para quando o chamador precisa do tipo original."""
        col = self.mapa.get(canonico)
        return None if col is None else row.get(col)

    def concatenar(self, row: Dict[str, Any], canonicos: Iterable[str], sep: str = " ; ") -> str:
        """Junta os campos informados, descartando os vazios."""
        partes = [self.valor(row, c) for c in canonicos]
        return sep.join(p for p in partes if p)

    def relatorio(self) -> Dict[str, Any]:
        """Resumo do que foi resolvido, para o relatorio de auditoria."""
        return {
            "total_colunas_arquivo": len(self.colunas_originais),
            "campos_resolvidos": dict(sorted(self.mapa.items())),
            "campos_ausentes": sorted(self.ausentes),
        }
