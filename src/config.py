"""
Configurações e constantes para a pipeline de itens do ENEM.
"""

import re
from pathlib import Path

# Cores regulares oficiais de cadernos de prova (Primeira Aplicação)
REGULAR_COLORS = ['AZUL', 'AMARELO', 'AMARELA', 'BRANCO', 'BRANCA', 'ROSA', 'CINZA', 'VERDE']

def get_day_for_area(area: str, year: int) -> int:
    """
    Retorna o dia de prova correspondente à Área do Conhecimento considerando
    a mudança histórica de calendário do ENEM em 2017:
    - 2009 a 2016: Dia 1 (Sábado) = CN, CH; Dia 2 (Domingo) = LC, MT
    - 2017 a 2024: Dia 1 (1º Domingo) = LC, CH; Dia 2 (2º Domingo) = CN, MT
    """
    area = area.upper().strip()
    if year <= 2016:
        if area in ('CN', 'CH'):
            return 1
        elif area in ('LC', 'MT'):
            return 2
    else:
        if area in ('LC', 'CH'):
            return 1
        elif area in ('CN', 'MT'):
            return 2
    raise ValueError(f"Área desconhecida '{area}' para o ano {year}")

# Mapeamento padrão (pós-2017) mantido por compatibilidade
AREA_TO_DAY = {
    'LC': 1,
    'CH': 1,
    'CN': 2,
    'MT': 2
}

# Área e dia alvo para extração focada em Matemática
TARGET_AREA = 'MT'
MATH_EXAM_DAY = 2

# Ordem determinística de preferência para seleção unária de cores
PREFERRED_COLORS = ['AMARELO', 'AZUL', 'CINZA', 'ROSA', 'VERDE', 'BRANCO']

# Termos que identificam estritamente provas adaptadas e provas digitais (exclusão permanente)
ADAPTED_TEST_KEYWORDS = [
    'digital',
    'adaptad',
    'ledor',
    'brail',
    'ampliad',
    'superampliad',
    'leitor tela',
    'dosvox',
    'nvda',
    'libras',
    'videoprova',
    'especial'
]

# Termos que identificam provas de Reaplicação e PPL (Segunda Aplicação - P2)
PPL_TEST_KEYWORDS = [
    'reaplica',
    'ppl',
    'oportunidade',
    'segunda',
    '2ª',
    '2a'
]

# Mantido por retrocompatibilidade (aponta para provas excluídas)
EXCLUDED_TEST_KEYWORDS = ADAPTED_TEST_KEYWORDS

# Expressões regulares para limpeza de ruídos nos PDFs das provas
WATERMARK_REGEX = re.compile(r'(ENEM\s*\d{4}\s*){2,}', re.IGNORECASE)
BARCODE_REGEX = re.compile(r'\*[0-9A-Za-z_–-]+\*', re.IGNORECASE)
RUNNING_FOOTER_REGEX = re.compile(r'CADERNO\s+\d+\s*[-–—]\s*(AZUL|AMARELO|VERDE|BRANCO|CINZA|ROSA)', re.IGNORECASE)
RUNNING_HEADER_REGEX = re.compile(r'^(CIÊNCIAS|MATEMÁTICA|LINGUAGENS|REDAÇÃO|REDACAO)', re.IGNORECASE)

# Expressão para identificar rodapés e cabeçalhos com área e dia (por extenso ou siglas CH, CN, LC, MT, RED)
RUNNING_AREA_DAY_REGEX = re.compile(
    r'^(?:'
    r'(?:CIÊNCIAS(?:\s+DA\s+NATUREZA|\s+HUMANAS)?|MATEMÁTICA|LINGUAGENS|REDAÇÃO|REDACAO)\b.*?(?:DIA|CADERNO|DOMINGO|SÁBADO)|'
    r'(?:CH|CN|LC|MT|RED)\s*[-–—|]\s*[12][ºo°]?\s*dia|'
    r'[12][ºo°]?\s*dia(?:\s*[-–—|]\s*CADERNO|\s*$)'
    r')',
    re.IGNORECASE
)

# Expressão para identificar e remover resíduos de rascunho de redação (íntegros ou fatiados pelo corte de colunas)
REDACAO_DRAFT_REGEX = re.compile(
    r'\s*(?:'
    r'RASCUNH?[\s\S]*?(?:FOLHA\s+DE\s+REDA[ÇC][ÃA]O|DA[ÇC][ÃA]O|A[ÇC][ÃA]O|Folha\s+de\s+Reda[çc][ãa]o)|'
    r'\bRASCUNHO\s+DA\s+REDA[ÇC][ÃA]O\b.*|'
    r'\bTranscreva\s+a\s+sua\s+Reda[çc][ãa]o\b.*|'
    r'\b(?:o\s+)?(?:para\s+a\s+)?Folha\s+de\s+Reda[çc][ãa]o\b.*'
    r').*$',
    re.IGNORECASE
)

# Expressão para remover resíduos de rodapés/cabeçalhos colados no final das alternativas
ALT_FOOTER_CLEANUP_REGEX = re.compile(
    r'(?:'
    r'[•\-–—|\\bullet]?\s*(?:CIÊNCIAS(?:\s+DA\s+NATUREZA|\s+HUMANAS)?|MATEMÁTICA|LINGUAGENS|REDAÇÃO|REDACAO)\b.*$|'
    r'\b(?:CIÊNCIAS(?:\s+DA\s+NATUREZA|\s+HUMANAS)?|MATEMÁTICA|LINGUAGENS|REDAÇÃO|REDACAO)\s*[-–—|]\s*[12][ºo°]?\s*dia.*$|'
    r'\b(?:\d+\s*)?(?:CH|CN|LC|MT|RED)\s*[-–—|\\bullet]?\s*[12][ºo°]?\s*dia.*$|'
    r'\b(?:CIÊNCIAS(?:\s+DA\s+NATUREZA|\s+HUMANAS)?|MATEMÁTICA|LINGUAGENS[,\s]+CÓDIGOS)\s+E\s+SUAS\s+TECNOLOGIAS.*$|'
    r'\bQuestões\s+de\s+\d+\s+a\s+\d+.*$|'
    r'[•\-–—|\\bullet]?\s*(?:CADERNO|RNO)\s+\d+.*$|'
    r'[•\-–—|\\bullet]?\s*[12][ºo°]?\s*dia\s*[-–—|]\s*CADERNO.*$|'
    r'[•\-–—|\\bullet]?\s*(?:AMARELO|AZUL|CINZA|ROSA|BRANCO|VERDE)?\s*[-–—|\\bullet]?\s*2[ªa]\s*APLICA[ÇC][ÃA]O.*$|'
    r'\b(?:AMARELO|AZUL|CINZA|ROSA|BRANCO|VERDE|ARELO)\s*[-–—|\\bullet]?\s*(?:P[ÁA]GINA\s*\d+|\d+\s*$)|\bP[ÁA]GINA\s*\d+\s*$|\b(?:AMARELO|AZUL|CINZA|ROSA|BRANCO|VERDE)\s*\d*\s*$|'
    r'\bTexto\s+(?:comum\s+)?para\s+as?\s+quest[õo]es?\s+\d+.*$|'
    r'\s*RASCUNH?[\s\S]*?(?:FOLHA\s+DE\s+REDA[ÇC][ÃA]O|DA[ÇC][ÃA]O|A[ÇC][ÃA]O|Folha\s+de\s+Reda[çc][ãa]o).*$'
    r')',
    re.IGNORECASE
)

# Expressão para identificar referências textuais explícitas a figuras, gráficos, mapas e esquemas
EXPLICIT_IMAGE_REGEX = re.compile(
    r'\b(?:'
    r'indicad[ao]s?\s+na\s+figura|'
    r'conforme\s+(?:a\s+)?figura|'
    r'como\s+(?:mostra|ilustra|se\s+v[eê])\s+a\s+figura|'
    r'como\s+na\s+figura|'
    r'ilustrad[ao]\s+na\s+figura|'
    r'apresentad[ao]\s+na\s+figura|'
    r'mostrad[ao]\s+na\s+figura|'
    r'representad[ao]\s+na\s+figura|'
    r'observada?\s+na\s+figura|'
    r'destacad[ao]s?\s+na\s+figura|'
    r'reproduzid[ao]\s+na\s+figura|'
    r'esboçad[ao]\s+na\s+figura|'
    r'v[eê]-se\s+na\s+figura|'
    r'o\s+gr[aá]fico\s+(?:a\s+seguir|abaixo|apresenta|mostra|indica|ilustra|representa)|'
    r'no\s+gr[aá]fico\s+(?:a\s+seguir|abaixo)|'
    r'os\s+gr[aá]ficos\s+(?:a\s+seguir|abaixo|apresentam|mostram)|'
    r'conforme\s+o\s+gr[aá]fico|'
    r'como\s+(?:mostra|ilustra)\s+o\s+gr[aá]fico|'
    r'no\s+esquema\s+(?:a\s+seguir|abaixo)|'
    r'conforme\s+o\s+esquema|'
    r'como\s+mostra\s+o\s+esquema|'
    r'indicad[ao]s?\s+no\s+esquema|'
    r'no\s+mapa\s+(?:a\s+seguir|abaixo)|'
    r'indicad[ao]s?\s+no\s+mapa'
    r')\b',
    re.IGNORECASE
)


# Expressão para localizar cabeçalhos de questão (suporta caixa alta/baixa e número em linha separada)
QUESTION_SPLIT_REGEX = re.compile(r'(?:^|\n)\s*QUEST[ÃA]O\s*[\n\r]*\s*(\d+)\s*', re.IGNORECASE)

# Expressão para linhas que podem iniciar uma alternativa
ALT_LINE_REGEX = re.compile(r'^\s*([A-E])(?:\t|\.|\)|\s+|$)(.*)$')

# Marcador para alternativas com conteúdo essencialmente gráfico
IMAGE_ALT_PLACEHOLDER = "[Figura / Imagem]"

# Anos suportados oficialmente pela pipeline
SUPPORTED_YEARS = list(range(2009, 2025))

# Nome padrão do arquivo consolidado contendo todas as edições
CONSOLIDATED_OUTPUT_FILENAME = "itens_prova_2009_2024_enriquecido.csv"

# Ordem canônica e padronizada das colunas para os arquivos enriquecidos
CANONICAL_COLUMNS = [
    'ANO_APLICACAO',
    'CO_POSICAO',
    'SG_AREA',
    'CO_ITEM',
    'TX_GABARITO',
    'CO_HABILIDADE',
    'IN_ITEM_ABAN',
    'TX_MOTIVO_ABAN',
    'NU_PARAM_A',
    'NU_PARAM_B',
    'NU_PARAM_C',
    'TX_COR',
    'CO_PROVA',
    'TP_LINGUA',
    'IN_ITEM_ADAPTADO',
    'TP_VERSAO_DIGITAL',
    'TP_APLICACAO',
    'REF_ARQUIVO_PDF',
    'DESC_ENUNCIADO',
    'DESC_ALTER_A',
    'DESC_ALTER_B',
    'DESC_ALTER_C',
    'DESC_ALTER_D',
    'DESC_ALTER_E',
    'IN_ITEM_IMAGEM'
]

# Colunas numéricas inteiras que devem ser preservadas sem decimais (.0)
INTEGER_COLUMNS = [
    'ANO_APLICACAO',
    'CO_POSICAO',
    'CO_ITEM',
    'CO_HABILIDADE',
    'IN_ITEM_ABAN',
    'CO_PROVA',
    'TP_LINGUA',
    'IN_ITEM_ADAPTADO',
    'TP_VERSAO_DIGITAL',
    'IN_ITEM_IMAGEM'
]

# Colunas decimais contínuas (parâmetros psicométricos da TRI)
FLOAT_COLUMNS = [
    'NU_PARAM_A',
    'NU_PARAM_B',
    'NU_PARAM_C'
]

