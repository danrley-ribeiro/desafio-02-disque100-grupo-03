#!/usr/bin/env python3
"""
=============================================================================
Classificador Avançado de Indício de Infração Penal - Disque 100 (2011–2026)
=============================================================================
Identifica e classifica se uma denúncia do Disque 100 apresenta indício de
infração penal (crimes e contravenções penais) ou se trata-se de demanda
direcionada prioritariamente à Rede de Proteção Social (CRAS, CREAS, Conselho
Tutelar, saúde e educação).

Compatibilidade Temporal Total:
  - Era 1 (2011 a 2020/1): colunas 'violacoes', 'cenario_local', etc.
  - Era 2 (2020/2 a 2026): colunas 'violacao', 'Denúncia_emergencial', etc.

Novos Recursos & Correções:
  1. Extração polimórfica e segura de textos (sem KeyError por ausência de colunas).
  2. Eliminação completa de falsos positivos de valores nulos ('NULL', 'NONE', '<NA>').
  3. Taxonomia penal expandida conforme o Código Penal e legislação especial
     (ECA, Estatuto do Idoso, Lei Maria da Penha, Lei de Tortura, Lei Henry Borel).
  4. Gradação de certeza do indício (ALTO, MEDIO, BAIXO / SOCIAL).
  5. Fundamentação legal explícita e órgão de encaminhamento prioritário.

Uso:
  python3 classificar_indicio_penal.py entrada.csv saida.csv
=============================================================================
"""

import sys
import re
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from colunas_disque100 import ResolvedorColunas, texto_limpo


# =============================================================================
# 1. TAXONOMIA JURÍDICO-PENAL DO DISQUE 100 (CÓDIGO PENAL E LEIS ESPECIAIS)
# =============================================================================

PENAL_TAXONOMY = [
    # 1. Crimes contra a Vida (Título I do Código Penal)
    {
        "categoria": "CRIMES_CONTRA_A_VIDA",
        "grau": "ALTO",
        "artigos": "Arts. 121, 122, 124-126 do Código Penal",
        "orgao": "DELEGACIA_DE_HOMICIDIOS_OU_POLICIA_CIVIL",
        "termos": [
            "HOMICÍDIO", "HOMICIDIO", "FEMINICÍDIO", "FEMINICIDIO",
            "INCITAÇÃO AO SUICÍDIO", "INCITACAO AO SUICIDIO", "INDUZIMENTO AO SUICÍDIO",
            "GENOCÍDIO", "GENOCIDIO", "ABORTO", "TENTATIVA DE HOMICÍDIO"
        ]
    },

    # 2. Crimes contra a Dignidade Sexual (Título VI do CP e ECA)
    {
        "categoria": "CRIMES_SEXUAIS",
        "grau": "ALTO",
        "artigos": "Arts. 213, 215-A, 216-A, 217-A, 218-B do CP; Arts. 240, 241, 244-A do ECA",
        "orgao": "DELEGACIA_ESPECIALIZADA_E_POLICIA_CIENTIFICA",
        "termos": [
            "ESTUPRO", "ESTUPRO DE VULNERÁVEL", "ESTUPRO VIRTUAL", "ESTUPRO CORRETIVO",
            "ABUSO SEXUAL", "IMPORTUNAÇÃO SEXUAL", "IMPORTUNACAO SEXUAL",
            "ASSÉDIO SEXUAL", "ASSEDIO SEXUAL", "PEDOFILIA", "PORNOGRAFIA INFANTIL",
            "EXPLORAÇÃO SEXUAL", "EXPLORACAO SEXUAL", "LASCÍVIA", "LASCIVIA",
            "VIOLÊNCIA SEXUAL MEDIANTE FRAUDE", "VIOLENCIA SEXUAL"
        ]
    },

    # 3. Crimes contra a Integridade Física e Tortura (CP, Lei 9.455/97, Lei Henry Borel)
    {
        "categoria": "CRIMES_INTEGRIDADE_FISICA_E_TORTURA",
        "grau": "ALTO",
        "artigos": "Lei 9.455/97 (Tortura); Arts. 129, 132, 136 CP; Lei 14.344/22; Art. 21 LCP",
        "orgao": "POLICIA_CIVIL_E_POLICIA_CIENTIFICA",
        "termos": [
            "TORTURA FÍSICA", "TORTURA FISICA", "TORTURA PSÍQUICA", "TORTURA PSIQUICA", "TORTURA",
            "LESÃO CORPORAL", "LESAO CORPORAL", "MAUS TRATOS", "MAUS-TRATOS",
            "AGRESSÃO", "AGRESSAO", "VIAS DE FATO", "EXPOSIÇÃO DE RISCO À SAÚDE",
            "EXPOSICAO DE RISCO A SAUDE", "PERIGO PARA A VIDA OU SAÚDE"
        ]
    },

    # 4. Crimes contra a Liberdade Individual e Tráfico (CP e Lei 11.343/06)
    {
        "categoria": "CRIMES_CONTRA_A_LIBERDADE_INDIVIDUAL",
        "grau": "ALTO",
        "artigos": "Arts. 147-A, 148, 149, 149-A do CP; Art. 239 do ECA; Lei 11.343/06",
        "orgao": "POLICIA_CIVIL_OU_FEDERAL",
        "termos": [
            "CÁRCERE PRIVADO", "CARCERE PRIVADO", "SEQUESTRO", "EXTORSÃO MEDIANTE SEQUESTRO",
            "CONDIÇÃO ANÁLOGA À DE ESCRAVO", "CONDICAO ANALOGA", "TRABALHO ESCRAVO",
            "TRÁFICO DE PESSOAS", "TRAFICO DE PESSOAS", "TRÁFICO DE CRIANÇAS", "TRAFICO DE CRIANCAS",
            "TRÁFICO DE MULHERES", "TRÁFICO DE DROGAS", "TRAFICO DE DROGAS",
            "ALICIAMENTO PARA O TRÁFICO", "STALKING", "PERSEGUIÇÃO", "PERSEGUICAO"
        ]
    },

    # 5. Ameaça, Coação e Extorsão
    {
        "categoria": "CRIMES_DE_AMEACA_E_COACAO",
        "grau": "MEDIO",
        "artigos": "Arts. 146, 147, 158, 344 do Código Penal",
        "orgao": "DELEGACIA_DE_POLICIA_CIVIL",
        "termos": [
            "AMEAÇA", "AMEACA", "COAÇÃO", "COACAO", "CONSTRANGIMENTO",
            "EXTORSÃO", "EXTORSAO", "CHANTAGEM"
        ]
    },

    # 6. Crimes contra a Honra, Injúria Racial e Racismo (CP e Lei 7.716/89)
    {
        "categoria": "CRIMES_CONTRA_A_HONRA_E_PRECONCEITO",
        "grau": "MEDIO",
        "artigos": "Arts. 138-140 do CP; Lei 7.716/89 (Racismo e Injúria Racial); STF ADO 26",
        "orgao": "DELEGACIA_DE_POLICIA_E_MINISTERIO_PUBLICO",
        "termos": [
            "INJÚRIA RACIAL", "INJURIA RACIAL", "RACISMO", "CALÚNIA", "CALUNIA",
            "DIFAMAÇÃO", "DIFAMACAO", "INJÚRIA", "INJURIA", "HOMOFOBIA", "TRANSFOBIA"
        ]
    },

    # 7. Crimes Patrimoniais e Financeiros (CP, Estatuto do Idoso e Estatuto da PCD)
    {
        "categoria": "CRIMES_PATRIMONIAIS_E_FINANCEIROS",
        "grau": "MEDIO",
        "artigos": "Arts. 155, 168, 171 CP; Arts. 102, 104 da Lei 10.741/03; Art. 89 Lei 13.146/15",
        "orgao": "DELEGACIA_DE_POLICIA_E_MINISTERIO_PUBLICO",
        "termos": [
            "APROPRIAÇÃO DE BENS", "APROPRIACAO DE BENS", "EXPROPRIAÇÃO", "EXPROPRIACAO",
            "RETENÇÃO DE SALÁRIO", "RETENCAO DE SALARIO", "RETENÇÃO DE CARTÃO", "RETENCAO DE CARTAO",
            "PATRIMONIAL>INDIVIDUAL", "VIOLÊNCIA PATRIMONIAL", "VIOLENCIA PATRIMONIAL",
            "ABUSO FINANCEIRO"
        ]
    },

    # 8. Crimes de Abandono Material e Omissão Penalmente Relevante
    {
        "categoria": "CRIMES_DE_ABANDONO_E_OMISSAO",
        "grau": "MEDIO",
        "artigos": "Arts. 133, 135, 244 do CP; Art. 98 da Lei 10.741/03 (Estatuto do Idoso)",
        "orgao": "MINISTERIO_PUBLICO_E_CONSELHO_TUTELAR",
        "termos": [
            "ABANDONO DE INCAPAZ", "ABANDONO MATERIAL", "ABANDONO DE IDOSO",
            "FÍSICA>ABANDONO", "FISICA>ABANDONO", "NEGLIGÊNCIA.ABANDONO", "OMISSÃO DE SOCORRO"
        ]
    }
]


# Campos textuais que descrevem a violacao relatada. A ordem nao altera o
# resultado: a taxonomia varre o texto concatenado.
CAMPOS_TEXTO_VIOLACAO = (
    "violacao", "subgrupo_violacao", "grupo_vulneravel", "motivacao",
)

# Cache de resolvedores por assinatura de colunas. `classificar_caso` pode ser
# chamada linha a linha sem resolvedor (uso interativo e notebook); sem o cache,
# cada chamada reconstruiria o indice de colunas.
_CACHE_RESOLVEDORES: Dict[Tuple[str, ...], ResolvedorColunas] = {}


def resolvedor_para(row: Any) -> ResolvedorColunas:
    """Devolve (e memoriza) o resolvedor correspondente as colunas desta linha."""
    try:
        chaves = tuple(row.keys())
    except AttributeError:  # pd.Series
        chaves = tuple(row.index)
    cached = _CACHE_RESOLVEDORES.get(chaves)
    if cached is None:
        cached = ResolvedorColunas(chaves)
        _CACHE_RESOLVEDORES[chaves] = cached
    return cached


def extrair_texto_caso(row: Any, resolvedor: Optional[ResolvedorColunas] = None) -> str:
    """Consolida em um unico texto as colunas que descrevem a violacao relatada."""
    res = resolvedor or resolvedor_para(row)
    return res.concatenar(row, CAMPOS_TEXTO_VIOLACAO)


def sinal_reforco_penal(
    row: Any,
    resolvedor: Optional[ResolvedorColunas] = None,
) -> Tuple[bool, str]:
    """
    Identifica sinais fáticos complementares que atestam natureza penal quando o
    texto da violação, isolado, não é típico. Valores que representam ausência de
    informação já foram descartados por `texto_limpo`.
    """
    res = resolvedor or resolvedor_para(row)

    # 1. Denúncia emergencial, risco de morte ou flagrante
    val = res.valor(row, "denuncia_emergencial")
    if any(k in val for k in ("RISCO IMINENTE", "FLAGRANTE", "SANGRAMENTO", "EMERGÊNCI", "EMERGENCI", "IMINENTE")):
        return True, "FLAGRANTE_OU_RISCO_IMINENTE"

    # 2. Cenário policial ou prisional
    val = res.valor(row, "cenario_violacao")
    if any(k in val for k in ("DELEGACIA", "PRESÍDIO", "PRESIDIO", "PENITENCIÁR", "PENITENCIAR", "CADEIA", "CUSTÓDIA", "CUSTODIA")):
        return True, "CENARIO_POLICIAL_OU_PRISIONAL"

    # 3. Suspeito ou vítima em cumprimento de pena ou custódia cautelar.
    #    Valores afirmativos observados na série: "PENA (RECLUSÃO)",
    #    "PENA (SEMI-ABERTO)", "PENA", "PREVENTIVA", "TEMPORÁRIA", "FLAGRANTE"
    #    e "MEDIDA SOCIOEDUCATIVA".
    for campo in ("suspeito_preso", "vitima_presa"):
        val = res.valor(row, campo)
        if any(k in val for k in (
            "RECLUS", "TEMPORÁRI", "TEMPORARI", "PREVENTIV", "FLAGRANTE",
            "SEMI-ABERTO", "SEMIABERTO", "PRISÃO", "PRISAO", "PENA",
            "SOCIOEDUCATIV", "REGIME",
        )):
            return True, "CUSTODIA_PRISIONAL_ATIVA"

    return False, "SEM_REFORCO_FATICO"


def classificar_caso(row: Any, resolvedor: Optional[ResolvedorColunas] = None) -> Dict[str, Any]:
    """
    Classifica um registro individual do Disque 100.

    `resolvedor` deve vir construído a partir do esquema do arquivo de origem
    quando a função é chamada em lote; sem ele, é resolvido e memorizado a
    partir das próprias chaves da linha.
    """
    res = resolvedor or resolvedor_para(row)
    texto = extrair_texto_caso(row, res)
    reforco_penal, motivo_reforco = sinal_reforco_penal(row, res)

    # 1. Avaliação pelas Regras da Taxonomia Jurídico-Penal
    for regra in PENAL_TAXONOMY:
        for termo in regra["termos"]:
            if termo in texto:
                return {
                    "indicio_penal": True,
                    "indicio_penal_texto": True,
                    "indicio_penal_reforco": reforco_penal,
                    "categoria_penal": regra["categoria"],
                    "grau_certeza": regra["grau"],
                    "fundamentacao_legal": regra["artigos"],
                    "orgao_prioritario": regra["orgao"],
                    "motivo_reforco": motivo_reforco
                }

    # 2. Contexto específico: violência psicológica contra mulher ou pessoa idosa.
    #    O módulo declarado pelo próprio Disque 100 prevalece sobre o gênero da
    #    vítima: uma denúncia registrada no módulo "Pessoa Idosa" é violência
    #    psicológica contra pessoa idosa, ainda que a vítima seja mulher.
    if any(k in texto for k in ("HUMILHAÇÃO", "HUMILHACAO", "HOSTILIZAÇÃO", "HOSTILIZACAO", "VIOLÊNCIA PSICOLÓGICA", "VIOLENCIA PSICOLOGICA")):
        grp = res.valor(row, "grupo_vulneravel")
        sexo = res.valor(row, "genero_vitima")

        if any(i in grp for i in ("IDOSA", "IDOSO")):
            return {
                "indicio_penal": True,
                "indicio_penal_texto": True,
                "indicio_penal_reforco": reforco_penal,
                "categoria_penal": "VIOLENCIA_PSICOLOGICA_CONTRA_IDOSO",
                "grau_certeza": "MEDIO",
                "fundamentacao_legal": "Arts. 96 e 99 da Lei 10.741/03 (Estatuto da Pessoa Idosa)",
                "orgao_prioritario": "DELEGACIA_DE_POLICIA_E_MINISTERIO_PUBLICO",
                "motivo_reforco": motivo_reforco
            }
        if "MULHER" in grp or "FEMIN" in sexo or sexo == "F":
            return {
                "indicio_penal": True,
                "indicio_penal_texto": True,
                "indicio_penal_reforco": reforco_penal,
                "categoria_penal": "VIOLENCIA_PSICOLOGICA_CONTRA_MULHER",
                "grau_certeza": "MEDIO",
                "fundamentacao_legal": "Art. 147-B do Código Penal (Lei 14.188/21 - Violência Psicológica)",
                "orgao_prioritario": "DELEGACIA_DA_MULHER_DPCAMI",
                "motivo_reforco": motivo_reforco
            }

    # 3. Caso o texto não seja típico, mas haja sinal de reforço fático indiscutível
    if reforco_penal:
        return {
            "indicio_penal": True,
            "indicio_penal_texto": False,
            "indicio_penal_reforco": True,
            "categoria_penal": f"INFRACAO_PENAL_REFUGIO_{motivo_reforco}",
            "grau_certeza": "ALTO",
            "fundamentacao_legal": "Notícia de Flagrante Delito, Risco Iminente ou Procedimento Prisional Ativo",
            "orgao_prioritario": "POLICIA_CIVIL_OU_MILITAR",
            "motivo_reforco": motivo_reforco
        }

    # 4. Caso típico da Rede de Proteção Social (CRAS, CREAS, Saúde, Educação, Conselho Tutelar)
    return {
        "indicio_penal": False,
        "indicio_penal_texto": False,
        "indicio_penal_reforco": False,
        "categoria_penal": "REDE_DE_PROTECAO_SOCIAL",
        "grau_certeza": "BAIXO",
        "fundamentacao_legal": "Demanda Assistencial, Cível ou Administrativa (Sem tipicidade penal primária)",
        "orgao_prioritario": "REDE_SOCIOASSISTENCIAL_CRAS_CREAS_E_CONSELHO",
        "motivo_reforco": motivo_reforco
    }


def classificar(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica o classificador penal enriquecido sobre o DataFrame fornecido."""
    resultados = [classificar_caso(row) for _, row in df.iterrows()]

    df["indicio_penal"] = [r["indicio_penal"] for r in resultados]
    df["indicio_penal_texto"] = [r["indicio_penal_texto"] for r in resultados]
    df["indicio_penal_reforco"] = [r["indicio_penal_reforco"] for r in resultados]
    df["categoria_penal"] = [r["categoria_penal"] for r in resultados]
    df["grau_certeza"] = [r["grau_certeza"] for r in resultados]
    df["fundamentacao_legal"] = [r["fundamentacao_legal"] for r in resultados]
    df["orgao_prioritario"] = [r["orgao_prioritario"] for r in resultados]

    return df


def main():
    parser = argparse.ArgumentParser(description="Classificador de Indício Penal para bases do Disque 100.")
    parser.add_argument("entrada", help="Caminho para a base CSV ou Parquet de entrada")
    parser.add_argument("saida", help="Caminho para o CSV de saída classificado")
    args = parser.parse_args()

    entrada_path = Path(args.entrada)
    if not entrada_path.exists():
        print(f"[-] Erro: Arquivo de entrada '{args.entrada}' não encontrado.")
        sys.exit(1)

    print(f"Lendo arquivo: {entrada_path.name}...")
    if entrada_path.suffix.lower() == ".parquet":
        df = pd.read_parquet(entrada_path)
    else:
        df = pd.read_csv(entrada_path, low_memory=False)

    print(f"Executando classificação penal em {len(df):,} registros...")
    df = classificar(df)

    saida_path = Path(args.saida)
    df.to_csv(saida_path, index=False)
    print(f"Base classificada salva em: '{saida_path}'")

    total = len(df)
    penal = df["indicio_penal"].sum()
    social = total - penal

    print("\n" + "=" * 65)
    print("RESULTADO CONSOLIDADO DA CLASSIFICAÇÃO")
    print("=" * 65)
    print(f"Total de registros analisados: {total:,}")
    print(f" • Com indício de infração penal: {penal:,} ({penal/total:.1%})")
    print(f" • Sem indício penal (Rede Social): {social:,} ({social/total:.1%})")

    print("\nDistribuição por Grau de Certeza:")
    for grau, cnt in df["grau_certeza"].value_counts().items():
        print(f"   [{grau:7s}]: {cnt:6,d} ({cnt/total:5.1%})")

    print("\nDistribuição por Categoria Jurídico-Penal:")
    for cat, cnt in df["categoria_penal"].value_counts().head(10).items():
        print(f"   - {cat}: {cnt:,} ({cnt/total:.1%})")

    print("\nÓrgãos de Encaminhamento Prioritário:")
    for org, cnt in df["orgao_prioritario"].value_counts().head(5).items():
        print(f"   • {org}: {cnt:,} ({cnt/total:.1%})")
    print("=" * 65)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        # Modo legado para compatibilidade direta de linha de comando
        entrada, saida = sys.argv[1], sys.argv[2]
        entrada_path = Path(entrada)
        if entrada_path.suffix.lower() == ".parquet":
            df = pd.read_parquet(entrada_path)
        else:
            df = pd.read_csv(entrada_path, low_memory=False)
        df = classificar(df)
        df.to_csv(saida, index=False)
        total = len(df)
        penal = df["indicio_penal"].sum()
        print(f"Total de registros: {total}")
        print(f"Com indício de infração penal: {penal} ({penal/total:.1%})")
        print(f"Sem indício (rede de proteção social): {total - penal} ({(total-penal)/total:.1%})")
    else:
        main()
