"""
Configurações e constantes para a pipeline de itens do ENEM.
"""

import re
from pathlib import Path

# Mapeamento oficial de Áreas do Conhecimento para o Dia de Prova
AREA_TO_DAY = {
    'LC': 1,  # Linguagens, Códigos e suas Tecnologias
    'CH': 1,  # Ciências Humanas e suas Tecnologias
    'CN': 2,  # Ciências da Natureza e suas Tecnologias
    'MT': 2   # Matemática e suas Tecnologias
}

# Cores regulares de cadernos de prova (Primeira Aplicação)
REGULAR_COLORS = ['AZUL', 'AMARELA', 'VERDE', 'CINZA', 'BRANCA']

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
RUNNING_FOOTER_REGEX = re.compile(r'CADERNO\s+\d+\s*[-–—]\s*(AZUL|AMARELO|VERDE|BRANCO|CINZA)', re.IGNORECASE)
RUNNING_HEADER_REGEX = re.compile(r'^(CIÊNCIAS|MATEMÁTICA|LINGUAGENS)', re.IGNORECASE)

# Expressão para localizar cabeçalhos de questão
QUESTION_SPLIT_REGEX = re.compile(r'(?:^|\n)\s*QUEST[ÃA]O\s+(\d+)\s*\t*\n*')

# Expressão para linhas que podem iniciar uma alternativa
ALT_LINE_REGEX = re.compile(r'^\s*([A-E])(?:\t|\.|\)|\s+|$)(.*)$')

# Marcador para alternativas com conteúdo essencialmente gráfico
IMAGE_ALT_PLACEHOLDER = "[Figura / Imagem]"
