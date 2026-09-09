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

# Termos que identificam provas não regulares (reaplicações e adaptações)
EXCLUDED_TEST_KEYWORDS = [
    'reaplica',
    'adaptada',
    'ledor',
    'braile',
    'libras',
    'ampliada',
    'superampliada',
    'leitor tela',
    'dosvox',
    'nvda'
]

# Expressões regulares para limpeza de ruídos nos PDFs das provas
WATERMARK_REGEX = re.compile(r'(ENEM\s*\d{4}\s*){2,}', re.IGNORECASE)
BARCODE_REGEX = re.compile(r'\*[0-9A-Z]+\*')
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

# Expressão para remover resíduos de rodapés/cabeçalhos colados no final das alternativas
ALT_FOOTER_CLEANUP_REGEX = re.compile(
    r'(?:'
    r'[•\-–—|]\s*(?:CIÊNCIAS(?:\s+DA\s+NATUREZA|\s+HUMANAS)?|MATEMÁTICA|LINGUAGENS|REDAÇÃO|REDACAO)\b.*$|'
    r'\b(?:CIÊNCIAS(?:\s+DA\s+NATUREZA|\s+HUMANAS)?|MATEMÁTICA|LINGUAGENS|REDAÇÃO|REDACAO)\s*[-–—|]\s*[12][ºo°]?\s*dia.*$|'
    r'\b(?:CH|CN|LC|MT|RED)\s*[-–—|]\s*[12][ºo°]?\s*dia.*$|'
    r'[•\-–—|]?\s*CADERNO\s+\d+.*$|'
    r'[•\-–—|]?\s*[12][ºo°]?\s*dia\s*[-–—|]\s*CADERNO.*$'
    r')',
    re.IGNORECASE
)

# Expressão para localizar cabeçalhos de questão (suporta caixa alta/baixa e número em linha separada)
QUESTION_SPLIT_REGEX = re.compile(r'(?:^|\n)\s*QUEST[ÃA]O\s*[\n\r]*\s*(\d+)\s*', re.IGNORECASE)

# Expressão para linhas que podem iniciar uma alternativa
ALT_LINE_REGEX = re.compile(r'^\s*([A-E])(?:\t|\.|\)|\s+|$)(.*)$')

# Marcador para alternativas com conteúdo essencialmente gráfico
IMAGE_ALT_PLACEHOLDER = "[Figura / Imagem]"
