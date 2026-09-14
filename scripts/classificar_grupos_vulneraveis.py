#!/usr/bin/env python3
"""
=============================================================================
Classificador de Grupos Vulneraveis - Disque 100 (2011-2026)
=============================================================================
Marca cada registro do Disque 100 quanto aos seis grupos prioritarios:
criancas e adolescentes, mulheres em violencia de genero, pessoas idosas,
pessoas com deficiencia, populacao LGBTQIA+ e sistema prisional / populacao
em situacao de rua.

As marcacoes NAO sao mutuamente exclusivas: uma adolescente com deficiencia
conta nos tres grupos correspondentes. `grupo_primario` resolve a exclusividade
por ordem de prioridade, apenas para visualizacoes que exigem particao.

Correcoes em relacao a versao anterior (todas verificadas contra os dados):

  1. Faixa etaria passou a ser interpretada pelos limites numericos, nao por
     rotulo literal. Havia tres formatos diferentes na serie:
       2011-2019 ...... "12 a 14 anos", "76 a 80 anos", "91 anos ou mais",
                        "Recem-nascido", "Nascituro"
       2020/1 ......... "05 a 09 anos", "00 a 1 ano", "80 anos ou mais"
       2020/2-2026 .... "08 ANOS" (idade cheia) e "40 A 44 ANOS" (faixa)
     A lista antiga ("0 A 4", "5 A 9", "10 A 14", "15 A 17") nao casava com
     nenhum dos dois formatos modernos e, pior, "0 A 4" era substring de
     "40 A 44 ANOS": 14.650 adultos de 40 a 44 anos entravam como criancas.
     No outro sentido, as faixas de idoso ("60 A 64" ... "80") nao casavam
     com "66 a 70 anos", "71 a 75 anos", "76 a 80 anos", "81 a 85 anos" nem
     "91 anos ou mais", perdendo os idosos de toda a era 2011-2019 que nao
     vinham identificados pelo modulo.

  2. Mulheres deixou de exigir simultaneamente genero feminino E palavra-chave
     de tipo de violencia. O modulo "Violencia contra a Mulher" do proprio
     Disque 100 e evidencia suficiente. Com a regra antiga, somada a coluna de
     genero nao resolvida, `is_mulher` era exatamente zero em 2020, 2021,
     2022, 2023, 2025 e 2026, enquanto o dado bruto traz 19.402 registros do
     modulo apenas em 2025-2026.

  3. Pessoa com deficiencia deixou de contar "NAO INFORMADO" como deficiencia
     declarada (tratamento centralizado em `colunas_disque100.texto_limpo`).

  4. A leitura de colunas passou pelo `ResolvedorColunas`, que reconhece as
     cinco grafias de genero, as quatro de faixa etaria e as tres de grupo
     vulneravel presentes nos arquivos.
=============================================================================
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from colunas_disque100 import ResolvedorColunas, texto_limpo

__all__ = [
    "GRUPOS_CANONICOS",
    "IDADE_MAXIMA_CRIANCA",
    "IDADE_MINIMA_IDOSA",
    "classificar_grupos",
    "faixas_etarias",
    "interpretar_faixa_etaria",
]


IDADE_MAXIMA_CRIANCA = 17   # ECA, Lei 8.069/1990, art. 2
IDADE_MINIMA_IDOSA = 60     # Estatuto da Pessoa Idosa, Lei 10.741/2003, art. 1

GRUPOS_CANONICOS: Tuple[str, ...] = (
    "is_crianca",
    "is_mulher",
    "is_idoso",
    "is_pcd",
    "is_lgbtqia",
    "is_prisional_rua",
)

# "12 a 14 anos", "00 a 1 ano", "40 A 44 ANOS"
_RE_INTERVALO = re.compile(r"(\d{1,3})\s*A\s*(\d{1,3})\s*ANOS?\b")
# "80 anos ou mais", "91 ANOS OU MAIS"
_RE_OU_MAIS = re.compile(r"(\d{1,3})\s*ANOS?\s*OU\s*MAIS")
# "08 ANOS", "3 ANO" - idade cheia, formato dos arquivos de 2020/2 em diante
_RE_IDADE_CHEIA = re.compile(r"^(\d{1,3})\s*ANOS?$")

_TERMOS_CRIANCA_IDADE = ("RECEM", "NASCITURO", "NASCIDO", "MENOR DE IDADE")
_TERMOS_IDOSO_IDADE = ("IDOS",)


def interpretar_faixa_etaria(valor: Any) -> Optional[Tuple[int, int]]:
    """
    Converte qualquer um dos formatos de faixa etaria da serie em um intervalo
    fechado de idades `(minimo, maximo)`, ou None quando nao ha informacao.

    >>> interpretar_faixa_etaria("12 a 14 anos")
    (12, 14)
    >>> interpretar_faixa_etaria("40 A 44 ANOS")
    (40, 44)
    >>> interpretar_faixa_etaria("08 ANOS")
    (8, 8)
    >>> interpretar_faixa_etaria("80 anos ou mais")
    (80, 120)
    >>> interpretar_faixa_etaria("00 a 1 ano")
    (0, 1)
    >>> interpretar_faixa_etaria("Recem-nascido")
    (0, 0)
    >>> interpretar_faixa_etaria("N/D") is None
    True
    """
    texto = texto_limpo(valor)
    if not texto:
        return None

    # A checagem de "ou mais" vem antes do intervalo: "91 ANOS OU MAIS" nao
    # deve ser lido como intervalo, e "80 A 84 ANOS OU MAIS" nao existe.
    m = _RE_OU_MAIS.search(texto)
    if m:
        return (int(m.group(1)), 120)

    m = _RE_INTERVALO.search(texto)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        return (min(lo, hi), max(lo, hi))

    m = _RE_IDADE_CHEIA.match(texto)
    if m:
        idade = int(m.group(1))
        return (idade, idade)

    if any(t in texto for t in _TERMOS_CRIANCA_IDADE):
        return (0, 0)

    return None


def faixas_etarias(valor: Any) -> Dict[str, bool]:
    """
    Indica se a faixa etaria informada pertence integralmente a infancia e
    adolescencia ou integralmente a populacao idosa.

    Faixas que atravessam o limite legal (por exemplo "56 a 60 anos", que
    mistura adultos e idosos) nao marcam nenhum dos dois: preferimos nao
    atribuir do que atribuir errado. Faixas abertas do tipo "MAIS DE 60" sao
    tratadas como idosas porque seu limite inferior ja satisfaz o estatuto.
    """
    texto = texto_limpo(valor)
    intervalo = interpretar_faixa_etaria(valor)

    crianca = False
    idoso = False

    if intervalo is not None:
        lo, hi = intervalo
        crianca = hi <= IDADE_MAXIMA_CRIANCA
        idoso = lo >= IDADE_MINIMA_IDOSA

    # Rotulos que declaram o grupo sem dar idade.
    if not crianca and ("CRIANCA" in texto or "CRIANÇA" in texto or "ADOLESC" in texto):
        crianca = True
    if not idoso and any(t in texto for t in _TERMOS_IDOSO_IDADE):
        idoso = True

    return {"crianca": crianca, "idoso": idoso}


_TERMOS_GENERO_FEMININO = ("FEMIN", "MULHER")
_TERMOS_VIOLENCIA_GENERO = (
    "DOMESTICA", "DOMÉSTICA", "CONJUGAL", "MARIA DA PENHA", "COMPANHEIR",
    "NAMORAD", "CONJUGE", "CÔNJUGE", "FEMINICIDIO", "FEMINICÍDIO",
    "147-B", "EX-MARIDO", "EX-COMPANHEIRO", "VIOLENCIA DE GENERO",
)
_TERMOS_LGBT = (
    "HOMO", "LESB", "LÉSB", "GAY", "BISSEX", "TRANS", "TRAVEST",
    "NAO BINARI", "NÃO BINÁRI", "QUEER", "ASSEXU", "PANSSEX",
)
_TERMOS_PRISIONAL_RUA = ("LIBERDADE", "PRISIONAL", "PRESIDIO", "PRESÍDIO", "RUA", "ENCARCERAD")
# Valores afirmativos observados no campo de custodia ao longo da serie:
# "PENA (RECLUSAO)", "PENA (SEMI-ABERTO)", "PENA", "PREVENTIVA", "TEMPORARIA",
# "FLAGRANTE" e "MEDIDA SOCIOEDUCATIVA". Os negativos ("NAO", "N/D",
# "NAO INFORMADO") ja foram descartados por `texto_limpo`.
_TERMOS_CUSTODIA = (
    "SIM", "PRESO", "PRESA", "PENA", "RECLUS", "SEMI-ABERTO", "SEMIABERTO",
    "PROVISORI", "PROVISÓRI", "PREVENTIV", "TEMPORARI", "TEMPORÁRI",
    "FLAGRANTE", "SOCIOEDUCATIV", "REGIME",
)


def _contem(texto: str, termos: Iterable[str]) -> bool:
    return any(t in texto for t in termos)


def classificar_grupos(
    row: Dict[str, Any],
    resolvedor: ResolvedorColunas,
) -> Dict[str, Any]:
    """
    Classifica um registro nos seis grupos prioritarios.

    `resolvedor` deve ter sido construido a partir do esquema do arquivo de
    origem, para que as grafias de coluna daquele ano sejam reconhecidas.
    Devolve as seis marcacoes booleanas, o `grupo_primario` exclusivo e a
    lista de sinais efetivamente disponiveis no registro, que alimenta o
    relatorio de cobertura da auditoria.
    """
    grupo = resolvedor.valor(row, "grupo_vulneravel")
    genero = resolvedor.valor(row, "genero_vitima")
    faixa_bruta = resolvedor.valor_bruto(row, "faixa_etaria_vitima")
    deficiencia = resolvedor.valor(row, "deficiencia_vitima")
    orientacao = resolvedor.valor(row, "orientacao_sexual_vitima")
    violacao = resolvedor.concatenar(row, ("violacao", "subgrupo_violacao"))
    motivacao = resolvedor.concatenar(row, ("motivacao", "relacao_vitima_suspeito"))
    vitima_presa = resolvedor.valor(row, "vitima_presa")

    idade = faixas_etarias(faixa_bruta)
    texto_violencia = f"{violacao} ; {motivacao}"

    # Crianca e adolescente: modulo declarado ou faixa etaria integralmente
    # abaixo de 18 anos.
    is_crianca = (
        "CRIANCA" in grupo or "CRIANÇA" in grupo or "ADOLESC" in grupo
        or idade["crianca"]
    )

    # Pessoa idosa: modulo declarado ou faixa etaria integralmente a partir
    # de 60 anos.
    is_idoso = ("IDOS" in grupo) or idade["idoso"]

    # Pessoa com deficiencia: modulo declarado ou deficiencia informada.
    # `texto_limpo` ja devolveu "" para "NAO", "NAO INFORMADO" e afins.
    is_pcd = ("DEFICIENCIA" in grupo or "DEFICIÊNCIA" in grupo) or bool(deficiencia)

    # Populacao LGBTQIA+: modulo declarado ou orientacao / identidade informada.
    is_lgbt = ("LGBT" in grupo) or _contem(orientacao, _TERMOS_LGBT)

    # Mulheres em violencia de genero: o modulo do Disque 100 basta por si.
    # Fora dele, exige-se genero feminino somado a contexto de violencia de
    # genero, para nao transformar toda vitima mulher em violencia domestica.
    is_mulher = (
        "MULHER" in grupo
        or (
            _contem(genero, _TERMOS_GENERO_FEMININO)
            and _contem(texto_violencia, _TERMOS_VIOLENCIA_GENERO)
        )
    )

    is_prisional_rua = (
        _contem(grupo, _TERMOS_PRISIONAL_RUA)
        or _contem(vitima_presa, _TERMOS_CUSTODIA)
    )

    if is_crianca:
        grupo_primario = "CRIANCAS_E_ADOLESCENTES"
    elif is_mulher:
        grupo_primario = "MULHERES_VIOLENCIA_GENERO"
    elif is_idoso:
        grupo_primario = "PESSOAS_IDOSAS"
    elif is_pcd:
        grupo_primario = "PESSOAS_COM_DEFICIENCIA"
    elif is_lgbt:
        grupo_primario = "POPULACAO_LGBTQIA+"
    elif is_prisional_rua:
        grupo_primario = "SISTEMA_PRISIONAL_E_RUA"
    else:
        grupo_primario = "GERAL_OUTROS"

    # Sinais disponiveis: distingue "nao pertence ao grupo" de "o arquivo nao
    # trazia como saber". E o que permite declarar, por exemplo, que 2023/1
    # nao tem coluna de grupo vulneravel.
    sinais: List[str] = []
    if grupo:
        sinais.append("grupo_vulneravel")
    if idade["crianca"] or idade["idoso"] or interpretar_faixa_etaria(faixa_bruta):
        sinais.append("faixa_etaria")
    if genero:
        sinais.append("genero")
    if deficiencia:
        sinais.append("deficiencia")
    if orientacao:
        sinais.append("orientacao_sexual")

    return {
        "grupo_primario": grupo_primario,
        "is_crianca": is_crianca,
        "is_mulher": is_mulher,
        "is_idoso": is_idoso,
        "is_pcd": is_pcd,
        "is_lgbtqia": is_lgbt,
        "is_prisional_rua": is_prisional_rua,
        "sinais_disponiveis": sinais,
    }
