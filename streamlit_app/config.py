"""
=============================================================================
Constantes, tema e contrato de filtros do painel do Disque 100 em SC
=============================================================================
Reune em um unico lugar o vocabulario do painel: unidades de medida, grupos
vulneraveis, escalas populacionais, faixas de distancia pericial, paleta de
cores e o contrato de filtros que a barra lateral devolve.

A paleta segue a instancia de referencia do metodo de visualizacao de dados:
oito matizes categoricas em ordem fixa, validadas para separacao em visao
normal e em deficiencia de cor, mais uma rampa sequencial de matiz unico para
magnitude. Os tons claros e escuros sao escolhidos por superficie, nao gerados
por inversao.
=============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# Pagina
# =============================================================================

PAGE_CONFIG: Dict[str, Any] = {
    "page_title": "Disque 100 em Santa Catarina",
    "layout": "wide",
    "initial_sidebar_state": "expanded",
}

TITULO = "Disque 100 em Santa Catarina"
SUBTITULO = (
    "Triagem entre indício de infração penal e demanda socioassistencial, "
    "cruzada com o Censo 2022 do IBGE e a rede da Polícia Científica"
)

# =============================================================================
# Paleta
# =============================================================================

# Ordem categorica fixa. Nunca reciclada: a partir do nono item, agregue em
# "Outros" em vez de gerar uma cor nova.
CATEGORICA: Tuple[str, ...] = (
    "#2a78d6",  # 1 azul
    "#eb6834",  # 2 laranja
    "#1baf7a",  # 3 verde-agua
    "#eda100",  # 4 amarelo
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 verde
    "#4a3aa7",  # 7 violeta
    "#e34948",  # 8 vermelho
)

# Rampa sequencial de matiz unico, do claro ao escuro, para magnitude continua
# (mapa coropletico e mapa de calor).
SEQUENCIAL_AZUL: Tuple[str, ...] = (
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab",
    "#184f95", "#104281", "#0d366b",
)

# Rampa ordinal de tres passos para as faixas de distancia pericial. O passo
# mais claro respeita o piso de contraste exigido para marcas ordinais.
ORDINAL_DISTANCIA: Tuple[str, ...] = ("#86b6ef", "#2a78d6", "#104281")

# Cor por natureza da ocorrencia. Sao duas categorias, nao dois polos: a
# distincao nao usa a paleta de estado, reservada para severidade.
COR_PENAL = CATEGORICA[0]
COR_SOCIAL = CATEGORICA[1]

# Camadas de contexto do mapa. Nao entram na paleta categorica: sao referencia
# geografica, nao series de dados, e por isso usam tinta neutra ou de destaque
# unico, sem competir com a escala de valor do coropleto.
COR_RODOVIA = "#52514e"
COR_PCI = "#0b0b0b"
COR_FOCO = CATEGORICA[1]

# Tinta e cromo do grafico
TINTA_PRIMARIA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
TINTA_DISCRETA = "#898781"
GRADE = "#e1e0d9"
LINHA_BASE = "#c3c2b7"
SUPERFICIE = "#fcfcfb"

FONTE = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

CUSTOM_CSS = """
<style>
.titulo-painel {
    font-size: 1.55rem;
    font-weight: 700;
    color: #0b0b0b;
    letter-spacing: -0.4px;
    margin-bottom: 0.15rem;
}
.subtitulo-painel {
    font-size: 0.92rem;
    color: #52514e;
    margin-bottom: 0.4rem;
}
.faixa-unidade {
    font-size: 0.8rem;
    color: #52514e;
    background: #f4f4f1;
    border-left: 3px solid #2a78d6;
    padding: 6px 10px;
    border-radius: 3px;
    margin-bottom: 1rem;
}
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
    height: 42px;
    white-space: pre-wrap;
    border-radius: 5px 5px 0 0;
    font-weight: 600;
    font-size: 13px;
    padding: 0 14px;
}
</style>
"""

# =============================================================================
# Unidade de medida
# =============================================================================

UNIDADE_REGISTROS = "registros"
UNIDADE_DENUNCIAS = "denuncias"

# Primeiro ano em que o identificador oficial da denuncia existe nos microdados.
# Antes disso so e possivel contar registros de violacao.
PRIMEIRO_ANO_COM_IDENTIFICADOR = 2021

UNIDADE_OPCOES: Dict[str, str] = {
    "Denúncias únicas (2021 em diante)": UNIDADE_DENUNCIAS,
    "Registros de violação (2011 em diante)": UNIDADE_REGISTROS,
}

UNIDADE_ROTULO: Dict[str, str] = {
    UNIDADE_REGISTROS: "registros de violação",
    UNIDADE_DENUNCIAS: "denúncias únicas",
}

# Sufixo de coluna por unidade: total e recorte penal.
UNIDADE_COLUNAS: Dict[str, Tuple[str, str]] = {
    UNIDADE_REGISTROS: ("total_registros", "total_penal"),
    UNIDADE_DENUNCIAS: ("denuncias_unicas", "denuncias_unicas_penal"),
}

AJUDA_UNIDADE = (
    "Cada linha dos microdados do Disque 100 é uma combinação de violação, vítima e "
    "suspeito, e não uma denúncia. Em 2026, Santa Catarina tem 95.850 registros de "
    "violação para 13.140 denúncias distintas. **Denúncias únicas** conta o "
    "identificador oficial da denúncia e é a unidade comparável com os balanços do "
    "MDHC, disponível de 2021 em diante. **Registros de violação** cobre toda a série "
    "desde 2011, mas o número de registros por denúncia cresceu ao longo do tempo e "
    "varia entre municípios, então não é comparável nem no tempo nem no território."
)

# =============================================================================
# Natureza da ocorrencia
# =============================================================================

NATUREZA_TOTAL = "total"
NATUREZA_PENAL = "penal"
NATUREZA_SOCIAL = "social"

NATUREZA_OPCOES: Dict[str, str] = {
    "Todas as ocorrências": NATUREZA_TOTAL,
    "Indício de infração penal": NATUREZA_PENAL,
    "Demanda socioassistencial": NATUREZA_SOCIAL,
}

NATUREZA_ROTULO: Dict[str, str] = {
    NATUREZA_TOTAL: "Todas as ocorrências",
    NATUREZA_PENAL: "Indício de infração penal",
    NATUREZA_SOCIAL: "Demanda socioassistencial",
}

# Rotulo do recorte penal conforme a unidade. No nivel da denuncia, "penal"
# significa "ao menos uma violacao tipificada": uma denuncia com sete violacoes
# das quais uma e tipificada entra por inteiro, e por isso a proporcao chega a
# 95%, contra 61% medidos em violacoes. A medida comparavel e a predominancia.
ROTULO_PENAL_POR_UNIDADE: Dict[str, str] = {
    UNIDADE_REGISTROS: "Com indício de infração penal",
    UNIDADE_DENUNCIAS: "Com algum indício penal",
}

ROTULO_SOCIAL_POR_UNIDADE: Dict[str, str] = {
    UNIDADE_REGISTROS: "Demanda socioassistencial",
    UNIDADE_DENUNCIAS: "Sem nenhum indício penal",
}

AJUDA_PENAL_DENUNCIA = (
    "Denúncia em que ao menos uma das violações relatadas é tipificada pela taxonomia. "
    "Uma denúncia com sete violações das quais apenas uma é penal entra por inteiro nesta "
    "contagem, de modo que a proporção fica bem acima da proporção medida em registros de "
    "violação. Para a medida comparável, veja a predominância penal logo abaixo do cartão."
)

AJUDA_PREDOMINANCIA = (
    "Denúncia em que a maioria das violações relatadas é tipificada como penal. É a "
    "medida de denúncia comparável à proporção penal apurada em registros de violação."
)

AJUDA_PENAL = (
    "Ocorrência cujo texto de violação relatada corresponde a um tipo penal previsto no "
    "Código Penal, no ECA (Lei 8.069/1990), na Lei Henry Borel (Lei 14.344/2022), no "
    "Estatuto da Pessoa Idosa (Lei 10.741/2003) ou na Lei Maria da Penha "
    "(Lei 11.340/2006). A classificação é automatizada por taxonomia de palavras-chave: "
    "indica onde há indício a apurar, não decisão jurídica, e sua precisão não foi medida."
)

AJUDA_SOCIAL = (
    "Ocorrência sem tipicidade penal reconhecida pela taxonomia: vulnerabilidade "
    "socioeconômica, conflito familiar, evasão escolar e negligência sem dolo aparente. "
    "Competência da rede SUAS (CRAS e CREAS), dos Conselhos Tutelares e da Defensoria "
    "Pública."
)

# =============================================================================
# Grupos vulneraveis
# =============================================================================

GRUPO_GERAL = "geral"

# Chave de coluna -> rotulo exibido. Um unico dicionario para todo o painel:
# os rotulos divergiam entre a barra lateral, a aba de grupos e o mapa.
GRUPO_ROTULOS: Dict[str, str] = {
    "criancas": "Crianças e adolescentes",
    "mulheres": "Mulheres em violência de gênero",
    "idosos": "Pessoas idosas",
    "pcd": "Pessoas com deficiência",
    "lgbt": "População LGBTQIA+",
    "prisional": "Sistema prisional e situação de rua",
}

# Marcacao correspondente no fato, usada para ler o relatorio de comparabilidade.
GRUPO_FLAG: Dict[str, str] = {
    "criancas": "is_crianca",
    "mulheres": "is_mulher",
    "idosos": "is_idoso",
    "pcd": "is_pcd",
    "lgbt": "is_lgbtqia",
    "prisional": "is_prisional_rua",
}

GRUPO_BASE_LEGAL: Dict[str, str] = {
    "criancas": "ECA, Lei 8.069/1990; Lei Henry Borel, Lei 14.344/2022",
    "mulheres": "Lei Maria da Penha, Lei 11.340/2006; Lei 14.188/2021",
    "idosos": "Estatuto da Pessoa Idosa, Lei 10.741/2003",
    "pcd": "Estatuto da Pessoa com Deficiência, Lei 13.146/2015",
    "lgbt": "Lei 7.716/1989 e ADO 26 do STF",
    "prisional": "Lei de Execução Penal, Lei 7.210/1984; Decreto 7.053/2009",
}

GRUPO_OPCOES: Dict[str, str] = {"Todos os grupos": GRUPO_GERAL}
GRUPO_OPCOES.update({rotulo: chave for chave, rotulo in GRUPO_ROTULOS.items()})

AVISO_GRUPOS_NAO_EXCLUSIVOS = (
    "Os grupos não são mutuamente exclusivos e não somam o total: uma adolescente com "
    "deficiência conta nos dois grupos, e parte dos registros não pertence a nenhum."
)

# Topico correspondente no mapa Folium pre-gerado.
FOLIUM_TOPIC_MAP: Dict[str, str] = {
    GRUPO_GERAL: "total",
    "criancas": "crianca",
    "mulheres": "mulher",
    "idosos": "idoso",
    "pcd": "pcd",
    "lgbt": "lgbt",
    "prisional": "preso",
}

# =============================================================================
# Escalas populacionais
# =============================================================================

ESCALA_OPCOES: Dict[str, int] = {
    "Por 10 mil habitantes": 10_000,
    "Por 100 mil habitantes": 100_000,
}

AJUDA_TAXA = (
    "Taxa calculada sobre a população residente do Censo 2022 do IBGE. Quando o recorte "
    "abrange mais de um ano, a taxa é anualizada dividindo pelo número de semestres "
    "efetivamente cobertos, para que períodos de extensão diferente sejam comparáveis. "
    "O denominador é um estoque populacional de um único ano; para os anos mais "
    "distantes de 2022 ele é apenas uma aproximação."
)

# =============================================================================
# Distancia ate a unidade pericial
# =============================================================================

FAIXA_PROXIMA_KM = 25.0
FAIXA_INTERMEDIARIA_KM = 50.0

FAIXA_PROXIMA = "Até 25 km da unidade pericial"
FAIXA_INTERMEDIARIA = "De 25 a 50 km da unidade pericial"
FAIXA_DISTANTE = "Acima de 50 km da unidade pericial"

FAIXAS_DISTANCIA: Tuple[str, str, str] = (FAIXA_PROXIMA, FAIXA_INTERMEDIARIA, FAIXA_DISTANTE)

FAIXA_COR: Dict[str, str] = {
    FAIXA_PROXIMA: ORDINAL_DISTANCIA[0],
    FAIXA_INTERMEDIARIA: ORDINAL_DISTANCIA[1],
    FAIXA_DISTANTE: ORDINAL_DISTANCIA[2],
}

ZONA_PCI_OPCOES: List[str] = ["Todas as faixas", FAIXA_PROXIMA, FAIXA_INTERMEDIARIA, FAIXA_DISTANTE]

AJUDA_RODOVIAS = (
    "Traçado esquemático dos corredores rodoviários federais e estaduais, com poucos "
    "vértices por eixo. Serve para situar as ligações entre regiões; não é a geometria "
    "oficial do DNIT ou do DEINFRA e não mede extensão nem tempo de percurso."
)

AJUDA_FOCOS = (
    "Municípios de maior incidência no recorte ativo, marcados no centroide municipal. "
    "Quando a métrica em foco é a taxa por habitante, o piso populacional também se "
    "aplica aqui, para que municípios pequenos demais não sejam apontados como foco."
)

AJUDA_PCI_MAPA = (
    "As 30 unidades da Polícia Científica de Santa Catarina: 9 superintendências "
    "regionais e 21 núcleos regionais, georreferenciadas a partir do portal oficial. "
    "O projeto não dispõe de base geográfica das delegacias da Polícia Civil."
)

AJUDA_DISTANCIA = (
    "Distância geodésica em linha reta entre o centroide do município e a unidade da "
    "Polícia Científica mais próxima, calculada por haversine. Não é distância "
    "rodoviária: em relevo de serra o percurso por estrada chega a uma vez e meia a "
    "distância em linha reta. O projeto não dispõe de modelo de tempo de deslocamento."
)

# =============================================================================
# Filtros da aba de dados
# =============================================================================

PORTE_OPCOES: List[str] = [
    "Todos os portes",
    "Até 20 mil habitantes",
    "De 20 mil a 50 mil habitantes",
    "De 50 mil a 100 mil habitantes",
    "Acima de 100 mil habitantes",
]

PERFIL_OPCOES: List[str] = [
    "Todos os perfis",
    "Predomínio penal, 60% ou mais",
    "Predomínio socioassistencial, 60% ou mais",
    "Taxa acima da média do recorte",
]

# Piso populacional para o ranking por taxa. Municípios muito pequenos produzem
# taxas instáveis: em Macieira, 1.778 habitantes, um punhado de denúncias
# complexas leva a taxa a quase metade da população.
POP_MINIMA_PADRAO = 20_000
POP_MINIMA_OPCOES: List[int] = [0, 5_000, 10_000, 20_000, 50_000]

AJUDA_POP_MINIMA = (
    "Municípios pequenos produzem taxas instáveis: poucas denúncias mudam a taxa em "
    "ordens de magnitude. O piso remove do ranking por taxa os municípios cuja "
    "população é pequena demais para sustentar a comparação. O volume absoluto e as "
    "tabelas não são afetados."
)

# =============================================================================
# Fontes oficiais
# =============================================================================

FONTES_OFICIAIS: List[Dict[str, str]] = [
    {
        "orgao": "Ministério dos Direitos Humanos e da Cidadania",
        "link": "https://www.gov.br/mdh/pt-br/ondh",
        "descricao": "Ouvidoria Nacional de Direitos Humanos: microdados abertos e balanços do Disque 100.",
    },
    {
        "orgao": "Instituto Brasileiro de Geografia e Estatística",
        "link": "https://sidra.ibge.gov.br/tabela/4714",
        "descricao": "Censo Demográfico 2022, tabela 4714: população residente dos 295 municípios de SC.",
    },
    {
        "orgao": "IBGE, API de Malhas",
        "link": "https://servicodados.ibge.gov.br/api/docs/malhas",
        "descricao": "Malha vetorial municipal e divisão regional de 2017 em regiões intermediárias e imediatas.",
    },
    {
        "orgao": "Polícia Científica de Santa Catarina",
        "link": "https://www.policiacientifica.sc.gov.br/unidades/",
        "descricao": "Catálogo das 30 unidades regionais: 9 superintendências e 21 núcleos.",
    },
    {
        "orgao": "Ministério do Desenvolvimento e Assistência Social",
        "link": "https://www.gov.br/mds/pt-br/acoes-e-programas/suas",
        "descricao": "Tipificação Nacional de Serviços Socioassistenciais, Resolução CNAS 109/2009, e parâmetros do SUAS.",
    },
    {
        "orgao": "Ministério da Justiça e Segurança Pública",
        "link": "https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica",
        "descricao": "Sistema Nacional de Informações de Segurança Pública e parâmetros de investigação.",
    },
]

# =============================================================================
# Contrato de filtros
# =============================================================================


@dataclass
class Filtros:
    """
    Estado completo dos filtros da barra lateral.

    Substitui a tupla posicional de treze elementos usada antes, em que
    reordenar um campo quebrava o painel sem erro visivel.
    """

    # Recorte temporal
    modo_temporal: str = "acumulado"
    ano: Optional[int] = None
    intervalo: Optional[Tuple[int, int]] = None
    label_periodo: str = ""
    year_param: str = "all"
    semestres_no_recorte: int = 0
    anos_no_recorte: List[int] = field(default_factory=list)
    recorte_tem_ano_parcial: bool = False

    # Recorte analitico
    unidade: str = UNIDADE_DENUNCIAS
    natureza: str = NATUREZA_TOTAL
    grupo: str = GRUPO_GERAL
    fator_pop: int = 10_000
    pop_minima: int = POP_MINIMA_PADRAO

    # Territorio
    regioes: List[str] = field(default_factory=list)
    region_code: str = "all"

    # Camadas de contexto do mapa
    camada_rodovias: bool = True
    camada_pci: bool = True
    camada_focos: bool = True
    quantidade_focos: int = 10
    camada_clusters: bool = True

    @property
    def rotulo_unidade(self) -> str:
        return UNIDADE_ROTULO[self.unidade]

    @property
    def rotulo_escala(self) -> str:
        return f"por {self.fator_pop // 1000} mil hab."

    @property
    def rotulo_grupo(self) -> str:
        return "Todos os grupos" if self.grupo == GRUPO_GERAL else GRUPO_ROTULOS[self.grupo]

    @property
    def rotulo_territorio(self) -> str:
        if not self.regioes:
            return "Santa Catarina"
        if len(self.regioes) == 1:
            return f"Região Intermediária de {self.regioes[0]}"
        return f"{len(self.regioes)} regiões intermediárias"

    def colunas(self) -> Tuple[str, str]:
        """Nomes das colunas de total e de recorte penal para a unidade e o grupo ativos."""
        if self.grupo == GRUPO_GERAL:
            return UNIDADE_COLUNAS[self.unidade]
        # As colunas por grupo existem apenas na unidade de registro de violação.
        return f"{self.grupo}_total", f"{self.grupo}_penal"

    def unidade_efetiva(self) -> str:
        """
        Unidade realmente aplicavel ao recorte.

        Denuncias unicas nao existem por grupo vulneravel nem antes de 2021, de
        modo que nesses casos o painel opera em registros de violacao e diz isso
        em vez de exibir zero.
        """
        if self.unidade == UNIDADE_DENUNCIAS and self.grupo != GRUPO_GERAL:
            return UNIDADE_REGISTROS
        return self.unidade
