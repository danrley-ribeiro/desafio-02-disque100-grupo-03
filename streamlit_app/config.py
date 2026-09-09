"""
Configurações, estilos e constantes institucionais do Sistema de Inteligência Territorial do Disque 100 SC.
"""

PAGE_CONFIG = {
    "page_title": "Inteligência Disque 100 - Governo de Santa Catarina",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

CUSTOM_CSS = """
<style>
.main-header {
    font-size: 1.7rem;
    font-weight: 800;
    color: #0f172a;
    margin-bottom: 0.1rem;
    letter-spacing: -0.5px;
}
.sub-header {
    font-size: 0.95rem;
    color: #475569;
    margin-bottom: 1.2rem;
    font-weight: 500;
}
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}
.stTabs [data-baseweb="tab"] {
    height: 44px;
    white-space: pre-wrap;
    border-radius: 6px 6px 0px 0px;
    font-weight: 600;
    font-size: 13.5px;
    padding: 0 16px;
}
.metric-container {
    border-left: 4px solid #3b82f6;
    padding: 10px 14px;
    background: #f8fafc;
    border-radius: 4px;
}
</style>
"""

# Opções de Filtro de Natureza da Ocorrência
NATUREZA_OPCOES = {
    "Total Geral (Consolidado)": "total",
    "Indício Penal (Crimes e Perícia Forense)": "penal",
    "Demanda Socioassistencial (Rede SUAS)": "social"
}

# Opções de Filtro por Grupos Vulneráveis
GRUPO_OPCOES = {
    "Todos os Grupos (Visão Geral)": "geral",
    "Crianças e Adolescentes (ECA)": "criancas",
    "Mulheres (Violência de Gênero / Doméstica)": "mulheres",
    "Pessoas Idosas (Estatuto da Pessoa Idosa)": "idosos",
    "Pessoas com Deficiência (Estatuto PCD)": "pcd",
    "População LGBTQIA+": "lgbt",
    "Sistema Prisional e Situação de Rua": "prisional"
}

# Mapeamento de Tópicos para Injeção no Mapa Folium (Leaflet)
FOLIUM_TOPIC_MAP = {
    "geral": "total",
    "criancas": "crianca",
    "mulheres": "mulher",
    "idosos": "idoso",
    "pcd": "pcd",
    "lgbt": "lgbt",
    "prisional": "preso"
}

# Escalas Populacionais Padronizadas
ESCALA_OPCOES = {
    "Taxa por 10.000 Habitantes (Padrão Estadual / Picos)": 10000,
    "Taxa por 50.000 Habitantes (Porte Médio Regional)": 50000,
    "Taxa por 100.000 Habitantes (Padrão SENASP / Atlas)": 100000
}

# Filtros do Explorer de Microdados (Aba 4)
PORTE_OPCOES = [
    "Todos os Portes",
    "Pequeno Porte I (< 20 mil hab)",
    "Pequeno Porte II (20 mil a 50 mil hab)",
    "Médio Porte (50 mil a 100 mil hab)",
    "Grande Porte (> 100 mil hab)"
]

PERFIL_SEVERIDADE_OPCOES = [
    "Todos os Perfis",
    "Predomínio Penal (> 60% Crimes)",
    "Predomínio Social (> 60% Rede SUAS)",
    "Picos Acima da Média Estadual"
]

ZONA_PCI_OPCOES = [
    "Todas as Zonas",
    "Vazios Críticos (> 50 km)",
    "Atenção Moderada (25 a 50 km)",
    "Resposta Imediata (< 25 km)"
]

# Textos de Ajuda Institucionais Jurídico-Operacionais
HELP_PENAL = (
    "Indício de Infração Penal: Ocorrências relatadas que configuram tipicidade "
    "prevista no Código Penal (arts. 121, 129, 136, 213, 217-A), no ECA (Lei 8.069/90), "
    "na Lei Henry Borel (Lei 14.344/22) ou no Estatuto da Pessoa Idosa (Lei 10.741/03). "
    "Exigem apuração imediata por órgãos de persecução policial (Polícia Civil de SC) "
    "e realização de exames de corpo de delito e coleta de vestígios pela Polícia Científica (PCI-SC)."
)

HELP_SOCIAL = (
    "Demanda Socioassistencial: Ocorrências caracterizadas por vulnerabilidades sociais, "
    "conflitos familiares, negligência socioeconômica ou evasão escolar, sem presença de dolo "
    "ou tipicidade penal imediata. São de competência da rede SUAS (CRAS e CREAS), "
    "Conselhos Tutelares e Defensoria Pública, não demandando inquérito policial ou perícia forense."
)

FONTES_OFICIAIS = [
    {
        "orgao": "Ministério dos Direitos Humanos e da Cidadania (MDHC)",
        "link": "https://www.gov.br/mdh/pt-br/ondh",
        "descricao": "Painel de Dados da Ouvidoria Nacional de Direitos Humanos e microdados abertos do Disque 100."
    },
    {
        "orgao": "Ministério da Justiça e Segurança Pública (MJSP)",
        "link": "https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/senasp",
        "descricao": "Sistema Nacional de Informações de Segurança Pública (SENASP) e protocolos de investigação."
    },
    {
        "orgao": "Ministério do Desenvolvimento e Assistência Social, Família e Combate à Fome (MDS)",
        "link": "https://www.gov.br/mds/pt-br/acoes-e-programas/SUAS",
        "descricao": "Tipificação Nacional de Serviços Socioassistenciais (Resolução CNAS nº 109/2009) e parâmetros da rede SUAS (CRAS/CREAS)."
    },
    {
        "orgao": "Instituto Brasileiro de Geografia e Estatística (IBGE)",
        "link": "https://sidra.ibge.gov.br/tabela/4714",
        "descricao": "Censo Demográfico 2022: População residente oficial dos 295 municípios catarinenses."
    },
    {
        "orgao": "Polícia Científica de Santa Catarina (PCI-SC)",
        "link": "https://www.policiacientifica.sc.gov.br/unidades/",
        "descricao": "Estrutura organizacional das 7 superintendências regionais e 23 núcleos periciais."
    },
    {
        "orgao": "Polícia Civil de Santa Catarina (PCSC)",
        "link": "https://pcporelas.pc.sc.gov.br/",
        "descricao": "Mapeamento das Delegacias de Proteção à Criança, Adolescente, Mulher e Idoso (DPCAMI)."
    }
]

