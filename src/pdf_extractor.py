"""
Módulo para extração de texto, enunciados, alternativas e detecção de imagens dos PDFs do ENEM.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import re
import pymupdf

from src.config import (
    WATERMARK_REGEX,
    BARCODE_REGEX,
    RUNNING_FOOTER_REGEX,
    RUNNING_HEADER_REGEX,
    RUNNING_AREA_DAY_REGEX,
    ALT_FOOTER_CLEANUP_REGEX,
    REDACAO_DRAFT_REGEX,
    QUESTION_SPLIT_REGEX,
    ALT_LINE_REGEX,
    IMAGE_ALT_PLACEHOLDER
)

def build_indesign_identity_h_cmap() -> str:
    """
    Constrói um CMap /ToUnicode para fontes Type0 /Identity-H geradas pelo Adobe InDesign
    que foram incorporadas sem tabela ToUnicode nos PDFs do ENEM.
    Mapeia:
    1. Caracteres ASCII 32..126 com deslocamento CID = ASCII - 29 (ex: CID 70 'F' -> 'c').
    2. Ligaduras tipográficas 'fi' (CID 0x00BF) e 'fl' (CID 0x00C0).
    3. Caracteres acentuados do português e pontuações especiais do InDesign.
    """
    mappings = []
    # ASCII 32 a 126
    for ascii_code in range(32, 127):
        cid = ascii_code - 29
        mappings.append((cid, chr(ascii_code)))

    extra_cids = {
        0x5F: 'à',
        0x65: 'É',
        0x69: 'á',
        0x6D: 'ã',
        0x6F: 'ç',
        0x70: 'é',
        0x72: 'ê',
        0x74: 'í',
        0x79: 'ó',
        0x7B: 'ô',
        0x7D: 'õ',
        0x7E: 'ú',
        0x82: '²',
        0x83: '³',
        0x87: '•',
        0x22: '”',
        0xB3: '“',
        0xBF: 'fi',
        0xC0: 'fl',
        0x28C: 'π',
    }
    for cid, ch in extra_cids.items():
        mappings.append((cid, ch))

    lines = [
        '/CIDInit /ProcSet findresource begin',
        '12 dict begin',
        'begincmap',
        '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
        '/CMapName /Custom-InDesign-Identity-H def',
        '/CMapType 2 def',
        '1 begincodespacerange',
        '<0000> <FFFF>',
        'endcodespacerange',
    ]

    chunk_size = 100
    for i in range(0, len(mappings), chunk_size):
        chunk = mappings[i:i + chunk_size]
        lines.append(f'{len(chunk)} beginbfchar')
        for cid, ch in chunk:
            uni_hex = ''.join(f'{ord(c):04X}' for c in ch)
            lines.append(f'<{cid:04X}> <{uni_hex}>')
        lines.append('endbfchar')

    lines.extend([
        'endcmap',
        'CMapName currentdict /CMap defineresource pop',
        'end',
        'end'
    ])
    return '\n'.join(lines)

def build_calibri_cmap() -> str:
    """
    Constrói um CMap /ToUnicode para fontes Calibri incorporadas em gráficos vetoriais do Excel
    (ex: gráfico do IBGE do ENEM 2010 P1).
    """
    calibri_map = {
        0x03EC: '0', 0x03ED: '1', 0x03EE: '2', 0x03EF: '3', 0x03F0: '4',
        0x03F1: '5', 0x03F2: '6', 0x03F3: '7', 0x03F4: '8', 0x03F5: '9',
        0x0045: 'N', 0x005E: 'S', 0x0012: 'C', 0x0057: 'P', 0x005A: 'R', 0x001C: 'E',
        0x0004: 'A', 0x0044: 'M',
        0x0102: 'a', 0x0104: 'á', 0x0106: 'ã', 0x010F: 'b', 0x0110: 'c', 0x011A: 'd',
        0x011E: 'e', 0x0128: 'f', 0x0150: 'g', 0x015A: 'h', 0x015D: 'i', 0x015F: 'í',
        0x016C: 'k', 0x016F: 'l', 0x0175: 'm', 0x0176: 'n', 0x017D: 'o', 0x017F: 'ó',
        0x0180: 'ô', 0x0181: 'õ', 0x0189: 'p', 0x018B: 'q', 0x018C: 'r', 0x0190: 's',
        0x019A: 't', 0x01B5: 'u', 0x01C0: 'v', 0x01CC: 'z',
        0x01D1: 'º', 0x03F8: '²', 0x0018: 'd',
        0x0372: '-', 0x037E: '(', 0x037F: ')', 0x0439: '%',
        0x0003: ' ', 0x0020: ' '
    }
    lines = [
        '/CIDInit /ProcSet findresource begin',
        '12 dict begin',
        'begincmap',
        '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
        '/CMapName /Custom-Calibri-Identity-H def',
        '/CMapType 2 def',
        '1 begincodespacerange',
        '<0000> <FFFF>',
        'endcodespacerange',
    ]

    items = list(calibri_map.items())
    chunk_size = 100
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        lines.append(f'{len(chunk)} beginbfchar')
        for cid, ch in chunk:
            uni_hex = ''.join(f'{ord(c):04X}' for c in ch)
            lines.append(f'<{cid:04X}> <{uni_hex}>')
        lines.append('endbfchar')

    lines.extend([
        'endcmap',
        'CMapName currentdict /CMap defineresource pop',
        'end',
        'end'
    ])
    return '\n'.join(lines)

def build_symbol_cmap() -> str:
    """
    Constrói um CMap /ToUnicode para fontes Symbol e SymbolMT Type0 /Identity-H.
    """
    symbol_map = {
        0x0020: ' ', 0x002B: '+', 0x002D: '-', 0x003D: '=', 0x002F: '/',
        0x0070: 'π', 0x0053: 'π', 0x0061: 'α', 0x0062: 'β', 0x0067: 'γ', 0x0064: 'δ',
        0x0071: 'θ', 0x006C: 'λ', 0x006D: 'μ', 0x0073: 'σ', 0x0077: 'ω',
        0x0044: 'Δ', 0x0050: 'Π', 0x0057: 'Ω',
        0x0098: '⋅', 0x00B7: '⋅', 0x00B4: '×', 0x00D7: '×', 0x0075: '×',
        0x00A3: '≤', 0x00B3: '≥', 0x00B9: '≠', 0x00BB: '≈', 0x00B1: '±',
        0x00B8: '÷', 0x00A5: '∞', 0x0066: '∞', 0x00B0: '°', 0x0087: '∅',
        0x0010: '-', 0x0028: '(', 0x0029: ')', 0x005B: '[', 0x005D: ']',
        # InDesign operadores e parênteses escaláveis para matrizes e fórmulas
        0x001F: '-', 0x001E: '=',
        0x001D: '(', 0x001C: '(', 0x001B: '(',
        0x001A: ')', 0x0019: ')', 0x0018: ')'
    }
    for n in range(10):
        symbol_map[0x0030 + n] = str(n)

    lines = [
        '/CIDInit /ProcSet findresource begin',
        '12 dict begin',
        'begincmap',
        '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
        '/CMapName /Custom-Symbol-Identity-H def',
        '/CMapType 2 def',
        '1 begincodespacerange',
        '<0000> <FFFF>',
        'endcodespacerange',
    ]

    items = list(symbol_map.items())
    chunk_size = 100
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        lines.append(f'{len(chunk)} beginbfchar')
        for cid, ch in chunk:
            uni_hex = ''.join(f'{ord(c):04X}' for c in ch)
            lines.append(f'<{cid:04X}> <{uni_hex}>')
        lines.append('endbfchar')

    lines.extend([
        'endcmap',
        'CMapName currentdict /CMap defineresource pop',
        'end',
        'end'
    ])
    return '\n'.join(lines)

# Mapeamento canônico de símbolos da fonte Symbol/SymbolMT para representação LaTeX
SYMBOL_MAP: Dict[str, str] = {
    'p': r'\pi', 'a': r'\alpha', 'b': r'\beta', 'g': r'\gamma', 'd': r'\delta',
    'q': r'\theta', 'l': r'\lambda', 'm': r'\mu', 's': r'\sigma', 'w': r'\omega',
    'D': r'\Delta', 'S': r'\pi', 'P': r'\Pi', 'W': r'\Omega',
    '\x98': r'\cdot', '\xb7': r'\cdot', '\xb4': r'\times', '\xd7': r'\times',
    '\xa3': r'\le', '\xb3': r'\ge', '\xb9': r'\ne', '\xbb': r'\approx', '\xb1': r'\pm',
    '\xb0': r'^\circ', '\xb8': r'\div', '\xa5': r'\infty',
    '\xce': r'\in', '\xcf': r'\notin', '\xcc': r'\subset', '\xcd': r'\supset',
    '\xc7': r'\cap', '\xc8': r'\cup',
    # Glifos de operadores e parênteses verticais do InDesign SymbolMT
    '\x1f': '-', '\x1e': '=',
    '\x1d': '(', '\x1c': '(', '\x1b': '(',
    '\x1a': ')', '\x19': ')', '\x18': ')',
    'π': r'\pi', 'Σ': r'\pi', 'α': r'\alpha', 'β': r'\beta', 'θ': r'\theta',
    '⋅': r'\cdot', '×': r'\times', '≤': r'\le', '≥': r'\ge', '≠': r'\ne', '≈': r'\approx', '±': r'\pm'
}

# Mapeamento de caracteres matemáticos Unicode em texto padrão para LaTeX
UNICODE_MATH_MAP: Dict[str, str] = {
    '²': '^2', '³': '^3', '¹': '^1', '⁰': '^0', '⁴': '^4', '⁵': '^5',
    '⁶': '^6', '⁷': '^7', '⁸': '^8', '⁹': '^9', 'ⁿ': '^n',
    '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4',
    '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',
    'π': r'\pi', 'Σ': r'\pi', '×': r'\times', '÷': r'\div', '±': r'\pm',
    '≤': r'\le', '≥': r'\ge', '≠': r'\ne', '≈': r'\approx',
    '•': r'\bullet', '°': r'^\circ', '⋅': r'\cdot', '√': r'\sqrt'
}

ADOBE_STANDARD_GLYPHS: Dict[str, str] = {
    'space': ' ', 'comma': ',', 'period': '.', 'hyphen': '-', 'colon': ':',
    'semicolon': ';', 'percent': '%', 'parenleft': '(', 'parenright': ')',
    'bracketleft': '[', 'bracketright': ']', 'plus': '+', 'equal': '=',
    'slash': '/', 'emdash': '—', 'endash': '–', 'exclam': '!', 'question': '?',
    'quotedblleft': '“', 'quotedblright': '”', 'quoteright': '’', 'dollar': '$',
    'bar': '|', 'degree': '°', 'twosuperior': '²', 'threesuperior': '³',
    'acute': '´', 'ordmasculine': 'º', 'Agrave': 'À', 'Aacute': 'Á', 'Atilde': 'Ã',
    'Ccedilla': 'Ç', 'Eacute': 'É', 'Iacute': 'Í', 'multiply': '×', 'Uacute': 'Ú',
    'agrave': 'à', 'aacute': 'á', 'acircumflex': 'â', 'atilde': 'ã', 'ccedilla': 'ç',
    'eacute': 'é', 'ecircumflex': 'ê', 'iacute': 'í', 'ntilde': 'ñ', 'oacute': 'ó',
    'ocircumflex': 'ô', 'otilde': 'õ', 'uacute': 'ú',
    'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
    'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
}
for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz':
    ADOBE_STANDARD_GLYPHS[c] = c

INDESIGN_EXTRA_CIDS: Dict[int, str] = {
    0x5F: 'à', 0x65: 'É', 0x66: 'à', 0x69: 'á', 0x6A: 'à', 0x6B: 'â',
    0x6D: 'ã', 0x6F: 'ç', 0x70: 'é', 0x72: 'ê', 0x74: 'í', 0x79: 'ó',
    0x7B: 'ô', 0x7D: 'õ', 0x7E: 'ú', 0x82: '²', 0x83: '³', 0x87: '•',
    0x22: '”', 0xB2: '²', 0xB3: '“', 0xB4: '”', 0xBF: 'fi', 0xC0: 'fl',
    0xF0: '²', 0x146: '–', 0x28C: 'π',
    106: 'à', 107: 'â', 135: '•', 178: '”', 179: '“', 180: '”',
    191: 'fi', 192: 'fl', 240: '²', 326: '–', 652: 'π'
}

def glyph_to_unicode(gname: str) -> Optional[str]:
    if gname in ('g167', 'g168', 'g169'):
        return '('
    if gname in ('g183', 'g184', 'g185'):
        return ')'
    if gname == 'g152':
        return '⋅'
    if gname == 'g32':
        return '='
    if gname == 'g16':
        return '-'
    if gname in ('g112', 'pi'):
        return 'π'
    if gname in ('g97', 'alpha'):
        return 'α'
    if gname in ('g98', 'beta'):
        return 'β'
    if gname in ('g113', 'theta'):
        return 'θ'
    if gname in ADOBE_STANDARD_GLYPHS:
        return ADOBE_STANDARD_GLYPHS[gname]
    if gname.startswith('g') and gname[1:].isdigit():
        cid = int(gname[1:])
        if cid in INDESIGN_EXTRA_CIDS:
            return INDESIGN_EXTRA_CIDS[cid]
        if 3 <= cid <= 97:
            return chr(cid + 29)
    return None

def build_tounicode_from_differences(enc_str: str) -> Optional[str]:
    m = re.search(r'/Differences\s*\[(.*?)\]', enc_str, re.DOTALL)
    if not m:
        return None
    tokens = m.group(1).split()
    code_to_uni = {}
    curr_code = 0
    for tok in tokens:
        if tok.isdigit():
            curr_code = int(tok)
        elif tok.startswith('/'):
            gname = tok[1:]
            u = glyph_to_unicode(gname)
            if u:
                code_to_uni[curr_code] = u
            curr_code += 1
    if not code_to_uni:
        return None
    lines = [
        '/CIDInit /ProcSet findresource begin',
        '12 dict begin',
        'begincmap',
        '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
        '/CMapName /Custom-Diff-ToUnicode def',
        '/CMapType 2 def',
        '1 begincodespacerange',
        '<00> <FF>',
        'endcodespacerange',
    ]
    items = sorted(code_to_uni.items())
    chunk_size = 100
    for i in range(0, len(items), chunk_size):
        chunk = items[i:i + chunk_size]
        lines.append(f'{len(chunk)} beginbfchar')
        for code, u in chunk:
            u_hex = ''.join(f'{ord(c):04X}' for c in u)
            lines.append(f'<{code:02X}> <{u_hex}>')
        lines.append('endbfchar')
    lines.extend([
        'endcmap',
        'CMapName currentdict /CMap defineresource pop',
        'end',
        'end'
    ])
    return '\n'.join(lines)

def repair_pdf_document_fonts(doc: pymupdf.Document) -> pymupdf.Document:
    """
    Inspeciona o documento PDF em busca de:
    1. Fontes Type0 /Identity-H que não possuem a tabela /ToUnicode CMap.
    2. Fontes Type1 com dicionário /Encoding contendo vetor /Differences com glifos
       InDesign (/g<CID>) que foram omitidos ou truncados no /ToUnicode original.
    Injeta dinamicamente o CMap adequado e recarrega o documento em memória se modificado.
    """
    indesign_bytes = build_indesign_identity_h_cmap().encode('ascii')
    calibri_bytes = build_calibri_cmap().encode('ascii')
    symbol_bytes = build_symbol_cmap().encode('ascii')

    modified = False
    for xref in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(xref)
            if '/Type /Font' in obj or '/Type/Font' in obj:
                # 1. Type0 / Identity-H sem ToUnicode
                if ('/Identity-H' in obj or '/Type0' in obj) and '/ToUnicode' not in obj:
                    if 'Calibri' in obj:
                        cmap_bytes = calibri_bytes
                    elif 'Symbol' in obj:
                        cmap_bytes = symbol_bytes
                    else:
                        cmap_bytes = indesign_bytes
                    cmap_xref = doc.get_new_xref()
                    doc.update_object(cmap_xref, f'<< /Length {len(cmap_bytes)} >>\nstream\n')
                    doc.update_stream(cmap_xref, cmap_bytes)
                    doc.xref_set_key(xref, 'ToUnicode', f'{cmap_xref} 0 R')
                    modified = True

                # 2. Type1 com /Differences contendo glifos InDesign /g<CID>
                m = re.search(r'/Encoding\s+(\d+)\s+0\s+R', obj)
                enc_str = doc.xref_object(int(m.group(1))) if m else obj
                if '/Differences' in enc_str and '/g' in enc_str:
                    cmap_str = build_tounicode_from_differences(enc_str)
                    if cmap_str:
                        cmap_bytes = cmap_str.encode('ascii')
                        cmap_xref = doc.get_new_xref()
                        doc.update_object(cmap_xref, f'<< /Length {len(cmap_bytes)} >>\nstream\n')
                        doc.update_stream(cmap_xref, cmap_bytes)
                        doc.xref_set_key(xref, 'ToUnicode', f'{cmap_xref} 0 R')
                        modified = True
        except Exception:
            pass

    if modified:
        return pymupdf.open(stream=doc.tobytes(), filetype='pdf')
    return doc


def clean_page_text(text: str) -> str:
    """
    Remove marcas d'água, códigos de barras e cabeçalhos/rodapés repetitivos da página,
    unificando números de questões quebrados em linhas distintas e normalizando ligaduras residuais.
    """
    # 0. Limpeza defensiva de caracteres de controle e ligaduras
    text = text.replace('\x03', ' ').replace('\x0f', ',').replace('\x11', '.')
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', text)
    text = re.sub(r'(\w)¿', r'\1fi', text)
    text = re.sub(r'¿(\w)', r'fi\1', text)

    # 1. Unifica 'Questão \n 14' em 'Questão 14' antes de qualquer filtro de linhas
    text = re.sub(r'(QUEST[ÃA]O)\s*[\n\r]+\s*(\d+)', r'\1 \2', text, flags=re.IGNORECASE)

    # 2. Remove marcas d'água do tipo ENEM2024ENEM2024... ou com variações/erros como ENEM20E4
    text = re.sub(r'(ENEM\s*20[0-9A-Z]{2}\s*){2,}', '', text, flags=re.IGNORECASE)
    # Remove combinações de ano e código de barras no cabeçalho (ex: '2010\n*azul25dom23*')
    text = re.sub(r'20\d{2}\s*\*[0-9A-Za-z_–-]+\*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\*[0-9A-Za-z_–-]+\*\s*20\d{2}', '', text, flags=re.IGNORECASE)
    # Remove códigos de barras *020325AZ2*
    text = BARCODE_REGEX.sub('', text)

    lines = []
    for line in text.split('\n'):
        s = line.strip()
        # Rodapé com menção a caderno ou dia
        if re.search(r'CADERNO\s+\d+', s, re.IGNORECASE) and any(c in s.upper() for c in ['AZUL', 'AMARELO', 'VERDE', 'BRANCO', 'CINZA', 'ROSA', 'PÁGINA', 'PAGINA']):
            continue
        if re.search(r'\b(?:AMARELO|AZUL|CINZA|ROSA|BRANCO|VERDE|ARELO)?\s*[-–—|]?\s*P[ÁA]GINA\s*\d+', s, re.IGNORECASE):
            continue
        # Números de página isolados
        if re.match(r'^\d{1,2}$', s):
            continue
        # Cabeçalhos ou rodapés com nome da área e dia (por extenso ou siglas CH, CN, LC, MT, RED)
        if RUNNING_AREA_DAY_REGEX.search(s):
            continue
        # Rascunho ou banner de redação isolado ou fragmentado pelo corte em duas colunas (mid_x)
        if re.match(r'^(?:RASCUNH?|[NC]?UNHO|DA\s+RED[A-Z]?|E?DA[ÇC][ÃA]O|A[ÇC][ÃA]O|(?:o\s+)?(?:para\s+a\s+)?Folha\s+de\s+Reda[çc][ãa]o\.?|RASCUNHO(?:\s+DA\s+REDA[ÇC][ÃA]O)?|Transcreva\s+a\s+sua\s+Reda[çc][ãa]o.*)$', s, re.IGNORECASE):
            continue
        # Banners de introdução de área e intervalo de questões
        if re.match(r'^(?:CIÊNCIAS(?:\s+DA\s+NATUREZA|\s+HUMANAS)?|MATEMÁTICA|LINGUAGENS[,\s]+CÓDIGOS)\s+E\s+SUAS\s+TECNOLOGIAS\s*$', s, re.IGNORECASE):
            continue
        if re.match(r'^Questões\s+de\s+\d+\s+a\s+\d+\s*$', s, re.IGNORECASE):
            continue
        lines.append(line)

    return '\n'.join(lines)

def format_alternative_latex(alt: str) -> str:
    """
    Formata o conteúdo de uma alternativa para garantir encapsulamento
    adequado de expressões e símbolos matemáticos em LaTeX ($ ... $).
    """
    alt = alt.strip()
    if not alt or alt == IMAGE_ALT_PLACEHOLDER:
        return alt

    # Remove resíduos de ponto de multiplicação solto no final da alternativa
    alt = re.sub(r'\s*\\cdot\s*$', '', alt).strip()
    alt = re.sub(r'\\cdot\s*\$$', '$', alt).strip()

    # Se o ponto final estiver dentro do delimitador $...$, remove ou move para fora
    m_dot_inside = re.match(r'^\$([^$]+)\.\$$', alt)
    if m_dot_inside:
        alt = f"${m_dot_inside.group(1).strip()}$"

    # Se já estiver encapsulado completamente entre $ ... $
    if alt.startswith('$') and alt.endswith('$') and alt.count('$') == 2:
        return alt

    # Verifica se contém expressões ou símbolos matemáticos
    math_symbols = [
        r'\frac', r'\sqrt', r'\pi', r'\cdot', r'\times', r'\begin{pmatrix}',
        '^', '_', r'\le', r'\ge', r'\ne', r'\pm', r'\circ', r'\div', r'\alpha', r'\beta', r'\theta'
    ]
    if any(sym in alt for sym in math_symbols):
        if '$' not in alt:
            has_trailing_dot = alt.endswith('.') and not alt.endswith('..')
            inner = alt[:-1].strip() if has_trailing_dot else alt
            return f"${inner}$"
    return alt

def sanitize_question_text(t: str) -> str:
    """
    Remove códigos de barras, menções a rascunho e anos residuais colados no final do enunciado,
    e formata variáveis e equações matemáticas em LaTeX ($ ... $).
    """
    t = BARCODE_REGEX.sub('', t)
    t = REDACAO_DRAFT_REGEX.sub('', t)
    t = re.sub(r'\bRASCUNHO\s+DA\s+REDA[ÇC][ÃA]O.*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bTranscreva\s+a\s+sua\s+Reda[çc][ãa]o.*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\bRascunho\b.*$', '', t, flags=re.IGNORECASE)
    t = re.sub(r'(?:ENEM\s*)?20\d{2}\s*$', '', t, flags=re.IGNORECASE)

    # Remove resíduos de parênteses escaláveis vazios
    t = re.sub(r'\(\s*\)', ' ', t)

    # Se há delimitadores $, processa variáveis e potências isoladas apenas fora das fórmulas já existentes
    parts = t.split('$')
    if len(parts) > 1 and len(parts) % 2 == 1:
        for i in range(0, len(parts), 2):
            seg = parts[i]
            # Envolve variáveis indexadas isoladas: M_{1} -> $M_{1}$, E_{2} -> $E_{2}$, S_{1} -> $S_{1}$
            seg = re.sub(r'(?<![\$\w])([A-Za-z]_[0-9A-Za-z]+|[A-Za-z]_\{[^}]+\})(?![\$\w])', r'$\1$', seg)
            # Envolve potências numéricas isoladas: 10^{3} -> $10^{3}$
            seg = re.sub(r'(?<![\$\w])(\d+(?:\^[0-9A-Za-z]+|\^\{[^}]+\}))(?![\$\w])', r'$\1$', seg)
            parts[i] = seg
        t = '$'.join(parts)
    else:
        t = re.sub(r'(?<![\$\w])([A-Za-z]_[0-9A-Za-z]+|[A-Za-z]_\{[^}]+\})(?![\$\w])', r'$\1$', t)
        t = re.sub(r'(?<![\$\w])(\d+(?:\^[0-9A-Za-z]+|\^\{[^}]+\}))(?![\$\w])', r'$\1$', t)

    # Converte funções matemáticas padrão para notação LaTeX apenas se não precedidas por barra invertida
    t = re.sub(r'(?<!\\)\b(log|ln|sen|cos|tg)\b', lambda m: f"\\{m.group(1)}", t)

    # Unifica múltiplos delimitadores adjacentes $$ -> $
    t = re.sub(r'\$\$+', '$', t)

    return " ".join(t.split())

def parse_question_body(q_text: str) -> Tuple[str, Dict[str, str]]:
    """
    Segmenta o corpo de uma questão em enunciado e alternativas A, B, C, D, E.
    Suporta:
    1. Alternativas padrão linha a linha (A, B, C, D, E)
    2. Alternativas inline e em sub-colunas (A B C D E ou A D B E C)
    3. Alternativas puramente gráficas (ex.: 'A D B E C' no final)
    """
    lines = q_text.split('\n')
    candidates = []

    for idx, l in enumerate(lines):
        m = ALT_LINE_REGEX.match(l)
        if m:
            candidates.append((idx, m.group(1), m.group(2).strip()))

    valid_seqs = []
    for a_pos, (idx_a, let_a, text_a) in enumerate(candidates):
        if let_a != 'A':
            continue
        seq = [(idx_a, 'A', text_a)]
        curr_expected = 'B'
        for idx_next, let_next, text_next in candidates[a_pos + 1:]:
            if let_next == curr_expected:
                seq.append((idx_next, let_next, text_next))
                if curr_expected == 'B': curr_expected = 'C'
                elif curr_expected == 'C': curr_expected = 'D'
                elif curr_expected == 'D': curr_expected = 'E'
                elif curr_expected == 'E': break

        if len(seq) == 5:
            max_dist = max(seq[k + 1][0] - seq[k][0] for k in range(4))
            valid_seqs.append((max_dist, seq))

    if valid_seqs:
        # Prioriza sequências mais compactas e mais ao final do texto
        valid_seqs.sort(key=lambda x: (x[0], -x[1][0][0]))
        best_seq = valid_seqs[0][1]

        first_line_idx = best_seq[0][0]
        enunciado_raw = "\n".join(lines[:first_line_idx]).strip()

        alts = {}
        for i in range(5):
            cur_line_idx, let, cur_text = best_seq[i]
            next_line_idx = best_seq[i + 1][0] if i < 4 else len(lines)
            more_lines = lines[cur_line_idx + 1:next_line_idx]
            alt_content = " ".join([cur_text] + [l.strip() for l in more_lines]).strip()

            # Remove qualquer resíduo de marca d'água ou rodapé no final da alternativa
            alt_content = re.sub(r'(ENEM\s*20[0-9A-Z]{2}\s*)+.*$', '', alt_content, flags=re.IGNORECASE).strip()
            alt_content = ALT_FOOTER_CLEANUP_REGEX.sub('', alt_content).strip()
            alt_content = REDACAO_DRAFT_REGEX.sub('', alt_content).strip()
            alt_content = BARCODE_REGEX.sub('', alt_content).strip()
            alt_content = re.sub(r'\bRASCUNHO\s+DA\s+REDA[ÇC][ÃA]O.*$', '', alt_content, flags=re.IGNORECASE).strip()
            alt_content = re.sub(r'\bTranscreva\s+a\s+sua\s+Reda[çc][ãa]o.*$', '', alt_content, flags=re.IGNORECASE).strip()
            alt_content = re.sub(r'\bRascunho\b.*$', '', alt_content, flags=re.IGNORECASE).strip()
            # Se a alternativa não for apenas um ano (ex: '2013' ou 'A 2005'), remove ano residual do rodapé/cabeçalho
            if not re.match(r'^(?:[A-E]\s*)?20\d{2}$', alt_content.strip()):
                alt_content = re.sub(r'\s+20\d{2}\s*$', '', alt_content).strip()

            if not alt_content:
                alt_content = IMAGE_ALT_PLACEHOLDER
            else:
                alt_content = format_alternative_latex(alt_content)
            alts[let] = alt_content

        clean_enunciado = sanitize_question_text(enunciado_raw)
        return clean_enunciado, alts

    # 2. Padrão visual com letras no final (ex: 'A D B E C', 'D A B E C', 'A B C D E', etc.)
    m_visual = re.search(r'\b(?:[A-E]\s+){4}[A-E](?:\s+MN\s+MO|\s+2ª\s*aplicação)?\s*$', q_text, re.IGNORECASE)
    if m_visual:
        enun = q_text[:m_visual.start()].strip()
        alts = {let: IMAGE_ALT_PLACEHOLDER for let in 'ABCDE'}
        return sanitize_question_text(enun), alts

    # 3. Padrão inline/sub-colunas com marcadores A-E
    pattern = re.compile(r'(?:(?<=[\s\n])|^)([A-E])(?=[\s\n\.\)\t]|$)')
    matches = list(pattern.finditer(q_text))
    for i in range(len(matches) - 5, -1, -1):
        group = matches[i:i + 5]
        letters = [m.group(1) for m in group]
        if set(letters) == {'A', 'B', 'C', 'D', 'E'}:
            start_pos = group[0].start()
            enun = q_text[:start_pos].strip()
            alts = {}
            for j in range(5):
                let = group[j].group(1)
                content_start = group[j].end()
                content_end = group[j + 1].start() if j < 4 else len(q_text)
                c_text = q_text[content_start:content_end].strip()
                c_text = ALT_FOOTER_CLEANUP_REGEX.sub('', c_text).strip()
                c_text = REDACAO_DRAFT_REGEX.sub('', c_text).strip()
                c_text = BARCODE_REGEX.sub('', c_text).strip()
                c_text = re.sub(r'\bRascunho\b.*$', '', c_text, flags=re.IGNORECASE).strip()
                c_text = re.sub(r'(ENEM\s*20[0-9A-Z]{2}\s*)+.*$', '', c_text, flags=re.IGNORECASE).strip()
                c_text = re.sub(r'(?:ENEM\s*)?20\d{2}\s*$', '', c_text, flags=re.IGNORECASE).strip()
                c_text = re.sub(r'2ª\s*aplicação.*$', '', c_text, flags=re.IGNORECASE).strip()
                if not c_text:
                    c_text = IMAGE_ALT_PLACEHOLDER
                else:
                    c_text = format_alternative_latex(c_text)
                alts[let] = c_text
            if all(k in alts for k in 'ABCDE'):
                return sanitize_question_text(enun), alts

    clean_enunciado = sanitize_question_text(q_text)
    return clean_enunciado, {}


def is_vector_figure_drawing(d: dict) -> bool:
    """
    Determina se um objeto de desenho vetorial (fitz drawing) representa
    uma figura matemática, gráfico cartesiano ou diagrama geométrico.
    Descarta bordas de página, cabeçalhos, rodapés, divisores decorativos,
    linhas de tabelas (puramente ortogonais) e bolhas de alternativas.
    """
    rect = d.get('rect')
    if not rect:
        return False
    w = rect.x1 - rect.x0
    h = rect.y1 - rect.y0

    # Margens e cabeçalho/rodapé
    if rect.y0 < 40 or rect.y1 > 745 or rect.x0 < 25 or rect.x1 > 570:
        return False

    # Bounding boxes excessivamente grandes (moldura da página ou colunas inteiras)
    if w > 260 or h > 450:
        return False

    # Elementos muito pequenos (bullets, bolhas de alternativas, traços minúsculos)
    if w < 15 and h < 15:
        return False

    # Linhas uniaxiais muito finas (linhas de tabela puramente horizontais ou verticais)
    if w < 3 or h < 3:
        return False

    for item in d.get('items', []):
        cmd = item[0]
        # Curvas de Bézier cúbicas (gráficos de funções, círculos, elipses, etc.)
        if cmd == 'c' and max(w, h) >= 15:
            return True
        # Linhas oblíquas / diagonais (geometria, eixos inclinados, polígonos)
        elif cmd == 'l':
            p1, p2 = item[1], item[2]
            dx = abs(p2.x - p1.x)
            dy = abs(p2.y - p1.y)
            if dx >= 6 and dy >= 6:
                return True
        # Quadriláteros oblíquos
        elif cmd == 'qu':
            q = item[1]
            pts = [q.ul, q.ur, q.lr, q.ll, q.ul]
            for p1, p2 in zip(pts[:-1], pts[1:]):
                if abs(p2.x - p1.x) >= 6 and abs(p2.y - p1.y) >= 6:
                    return True

    return False

def detect_images_per_question(doc: pymupdf.Document, has_duplicate_languages: bool) -> Set[Tuple[int, Optional[float]]]:
    """
    Identifica quais questões no documento PDF contêm imagens/figuras através de coordenadas espaciais,
    considerando tanto imagens raster (bitmap) quanto desenhos vetoriais (gráficos, geometrias, curvas).
    """
    q_regions = []
    seen_1 = 0

    for page_num in range(1, len(doc)):
        page = doc[page_num]
        mid_x = page.rect.width / 2.0
        blocks = page.get_text("blocks")

        left = [b for b in blocks if b[0] < mid_x and 40 < b[1] < 745]
        right = [b for b in blocks if b[0] >= mid_x and 40 < b[1] < 745]
        left.sort(key=lambda b: b[1])
        right.sort(key=lambda b: b[1])

        for col_idx, col_blocks in enumerate([left, right]):
            current_q = None
            current_lang = None
            q_start_y = 40.0
            for b in col_blocks:
                m = re.search(r'QUEST[ÃA]O\s*[\n\r]*\s*(\d+)', b[4], re.IGNORECASE)
                if m:
                    q_num = int(m.group(1))
                    lang = None
                    if has_duplicate_languages:
                        if q_num == 1:
                            seen_1 += 1
                        if q_num <= 5:
                            lang = 0.0 if seen_1 == 1 else 1.0

                    if current_q is not None:
                        q_regions.append({
                            'num': current_q,
                            'lang': current_lang,
                            'page': page_num,
                            'col': col_idx,
                            'y0': q_start_y,
                            'y1': b[1]
                        })
                    current_q = q_num
                    current_lang = lang
                    q_start_y = b[1]

            if current_q is not None:
                q_regions.append({
                    'num': current_q,
                    'lang': current_lang,
                    'page': page_num,
                    'col': col_idx,
                    'y0': q_start_y,
                    'y1': 745.0
                })

    questions_with_images = set()

    for page_num in range(1, len(doc)):
        page = doc[page_num]
        mid_x = page.rect.width / 2.0

        # 1. Detecção de imagens raster (bitmap / fotos / escaneadas)
        images = page.get_image_info()
        for img in images:
            b = img.get('bbox')
            if not b:
                continue
            w = b[2] - b[0]
            h = b[3] - b[1]

            # Ignora faixas laterais de margem, linhas finas e elementos fora da mancha de texto
            if w < 25 or h < 25 or b[0] > 550 or b[1] < 35 or b[3] > 745:
                continue

            img_x_mid = (b[0] + b[2]) / 2.0
            img_col = 0 if img_x_mid < mid_x else 1
            img_y_mid = (b[1] + b[3]) / 2.0

            for r in q_regions:
                if r['page'] == page_num and r['col'] == img_col:
                    if (r['y0'] - 20) <= img_y_mid <= (r['y1'] + 20):
                        questions_with_images.add((r['num'], r['lang']))
                        break

        # 2. Detecção de figuras vetoriais (gráficos de funções, esquemas geométricos, polígonos, curvas)
        for drawing in page.get_drawings():
            if not is_vector_figure_drawing(drawing):
                continue
            rect = drawing['rect']
            draw_x_mid = (rect.x0 + rect.x1) / 2.0
            draw_col = 0 if draw_x_mid < mid_x else 1
            draw_y_mid = (rect.y0 + rect.y1) / 2.0

            for r in q_regions:
                if r['page'] == page_num and r['col'] == draw_col:
                    if (r['y0'] - 20) <= draw_y_mid <= (r['y1'] + 20):
                        questions_with_images.add((r['num'], r['lang']))
                        break

    return questions_with_images

def format_span_tokens(spans_list: List[Dict[str, Any]]) -> str:
    """
    Combina uma lista de spans horizontais ordenados, detectando índices (subscritos)
    e potências (sobrescritos) baseando-se em tamanho relativo de fonte e linha de base.
    """
    if not spans_list:
        return ""
    base_size = max(s['size'] for s in spans_list)
    base_spans = [s for s in spans_list if s['size'] >= base_size * 0.85]
    base_orig_y = base_spans[0]['origin'][1] if base_spans else spans_list[0]['origin'][1]

    out = []
    for s in spans_list:
        t = s['text']
        if s['size'] < base_size * 0.85 and not s.get('is_math'):
            if s['origin'][1] > base_orig_y + 1.2:
                t = f"_{{{t}}}"
            elif s['origin'][1] < base_orig_y - 1.2:
                t = f"^{{{t}}}"
        out.append(t)
    res = "".join(out)
    res = re.sub(r'\^\{([^}]+)\}\^\{([^}]+)\}', r'^{\1\2}', res)
    res = re.sub(r'_\{([^}]+)\}_\{([^}]+)\}', r'_{\1\2}', res)
    return res

def extract_column_math_text(page: pymupdf.Page, clip_rect: pymupdf.Rect) -> str:
    """
    Extrai o conteúdo textual de uma coluna ou região da página reconstruindo
    fórmulas matemáticas em LaTeX bidimensionalmente (frações, raízes, potências, matrizes).
    """
    dict_data = page.get_text("dict", clip=clip_rect)
    spans = []
    for b in dict_data.get("blocks", []):
        if "lines" in b:
            for l in b["lines"]:
                for s in l["spans"]:
                    t = s["text"]
                    if not t:
                        continue
                    # Filtra cabeçalhos e rodapés de página por coordenadas verticais
                    if s["bbox"][3] <= 45.0 or s["bbox"][1] >= 737.0:
                        continue
                    # Filtra previamente códigos de barras e marcas d'água pesadas para não poluir índices
                    if "ENEM20" in t or re.search(r'\*[0-9A-Za-z_–-]+\*', t):
                        continue
                    font = s["font"]
                    is_lb = "Symbol" in font and (any(c in t for c in '\x1b\x1c\x1d') or any(ord(c) in (27, 28, 29) for c in t))
                    is_rb = "Symbol" in font and (any(c in t for c in '\x18\x19\x1a') or any(ord(c) in (24, 25, 26) for c in t))
                    if "Symbol" in font:
                        mapped = []
                        for ch in t:
                            o = ord(ch)
                            if o == 83 or ch == 'S' or o == 112:
                                mapped.append(r'\pi')
                            elif o in (152, 183, 8901) or ch == '⋅':
                                mapped.append(r'\cdot')
                            elif o == 117:
                                mapped.append(r'\times')
                            elif o == 16:
                                mapped.append('-')
                            elif o == 100:
                                mapped.append(r'\le')
                            elif o == 102:
                                mapped.append(r'\infty')
                            elif o == 135:
                                mapped.append(r'\varnothing')
                            elif o == 31 or ch == '\x1f':
                                mapped.append('-')
                            elif o == 30 or ch == '\x1e':
                                mapped.append('=')
                            elif o in (27, 28, 29) or ch in ('\x1b', '\x1c', '\x1d'):
                                mapped.append('(')
                            elif o in (24, 25, 26) or ch in ('\x18', '\x19', '\x1a'):
                                mapped.append(')')
                            elif ch in SYMBOL_MAP:
                                mapped.append(SYMBOL_MAP[ch])
                            else:
                                mapped.append(ch)
                        t = "".join(mapped)
                    else:
                        for u_ch, repl in UNICODE_MATH_MAP.items():
                            t = t.replace(u_ch, repl)

                    spans.append({
                        "text": t,
                        "bbox": list(s["bbox"]),
                        "origin": list(s.get("origin", (s["bbox"][0], s["bbox"][3]))),
                        "size": s["size"],
                        "font": font,
                        "is_lb": is_lb,
                        "is_rb": is_rb,
                        "used": False,
                        "is_math": "Symbol" in font or any(c in t for c in [r'\pi', r'\cdot', r'\times', r'\le', r'\infty', '^', '_'])
                    })

    # Coleta desenhos vetoriais na coluna (linhas horizontais de frações e radicais)
    hlines = []
    radicals = []
    for d in page.get_drawings():
        r = d['rect']
        if r.y0 < 40 or r.y1 > 737 or r.x1 < clip_rect.x0 or r.x0 > clip_rect.x1:
            continue
        items = d.get('items', [])
        lines = [it for it in items if it[0] == 'l']
        if len(lines) >= 4 and 8.0 <= (r.x1 - r.x0) <= 120.0 and 6.0 <= (r.y1 - r.y0) <= 35.0:
            horiz_top = [l for l in lines if abs(l[1].y - l[2].y) < 1.0 and abs(l[1].y - r.y0) < 3.0]
            if horiz_top:
                radicals.append((r, horiz_top[0]))
                continue

        for it in items:
            if it[0] == 'l':
                p1, p2 = it[1], it[2]
                if abs(p1.y - p2.y) < 1.0:
                    x0, x1 = min(p1.x, p2.x), max(p1.x, p2.x)
                    if 2.0 <= (x1 - x0) <= 80.0 and clip_rect.x0 - 5 <= x0 and x1 <= clip_rect.x1 + 5:
                        hlines.append((x0, (p1.y + p2.y) / 2.0, x1, (p1.y + p2.y) / 2.0))

    composite_elements = []

    # 1. Reconstrução de Radicais (\sqrt{...} ou \sqrt[n]{...})
    for r, h_line in radicals:
        rx0 = min(h_line[1].x, h_line[2].x)
        rx1 = max(h_line[1].x, h_line[2].x)

        # Detecta índice/grau do radical (pequeno texto localizado junto ao gancho inicial r.x0, r.y0)
        deg_spans = [
            s for s in spans if not s["used"]
            and (r.x0 - 3.0 <= s['bbox'][0] <= rx0)
            and (r.y0 - 4.0 <= s['bbox'][1] <= r.y0 + 5.0)
            and s['size'] <= 7.5
        ]
        deg_text = ""
        if deg_spans:
            for s in deg_spans:
                s["used"] = True
            deg_spans.sort(key=lambda s: s['bbox'][0])
            deg_text = format_span_tokens(deg_spans).strip()

        # Spans do radicando (devem estar sob a barra horizontal superior)
        rad_spans = [
            s for s in spans if not s["used"]
            and (r.y0 - 2.0 <= s['bbox'][1] <= r.y1 - 1.0)
            and (s['bbox'][3] <= r.y1 + 4.0)
            and (rx0 - 4.0 <= s['bbox'][0] and s['bbox'][2] <= rx1 + 4.0)
        ]
        if rad_spans:
            for s in rad_spans:
                s["used"] = True
            rad_spans.sort(key=lambda s: s['bbox'][0])
            content = format_span_tokens(rad_spans).strip()
            latex_rad = f"\\sqrt[{deg_text}]{{{content}}}" if deg_text else f"\\sqrt{{{content}}}"
            composite_elements.append({
                "text": latex_rad,
                "bbox": [r.x0, r.y0, max(r.x1, rad_spans[-1]['bbox'][2]), max(r.y1, rad_spans[-1]['bbox'][3])],
                "origin": [r.x0, r.y1],
                "size": max(s["size"] for s in rad_spans),
                "is_math": True
            })

    # 2. Reconstrução de Frações (\frac{num}{den})
    for x0, y, x1, _ in sorted(hlines, key=lambda h: (h[1], h[0])):
        num_spans = [
            s for s in spans if not s["used"]
            and (y - 16.0 <= s['bbox'][1] and s['bbox'][3] <= y + 1.5)
            and (x0 - 1.5 <= (s['bbox'][0] + s['bbox'][2]) / 2.0 <= x1 + 1.5)
        ]
        den_spans = [
            s for s in spans if not s["used"]
            and (y - 1.5 <= s['bbox'][1] and s['bbox'][3] <= y + 16.0)
            and (x0 - 1.5 <= (s['bbox'][0] + s['bbox'][2]) / 2.0 <= x1 + 1.5)
        ]

        num_comp = [
            c for c in composite_elements if not c.get("used")
            and (y - 16.0 <= c['bbox'][1] and c['bbox'][3] <= y + 1.5)
            and (x0 - 2.0 <= (c['bbox'][0] + c['bbox'][2]) / 2.0 <= x1 + 2.0)
        ]
        den_comp = [
            c for c in composite_elements if not c.get("used")
            and (y - 1.5 <= c['bbox'][1] and c['bbox'][3] <= y + 16.0)
            and (x0 - 2.0 <= (c['bbox'][0] + c['bbox'][2]) / 2.0 <= x1 + 2.0)
        ]

        all_num = num_spans + num_comp
        all_den = den_spans + den_comp

        if all_num and all_den:
            all_num.sort(key=lambda item: item['bbox'][0])
            all_den.sort(key=lambda item: item['bbox'][0])

            num_text = format_span_tokens(all_num).strip()
            den_text = format_span_tokens(all_den).strip()

            # Valida se é uma fração legítima (descarta linhas de tabelas com palavras em português ou textos longos)
            clean_num = re.sub(r'\\[a-zA-Z]+', '', num_text).strip()
            clean_den = re.sub(r'\\[a-zA-Z]+', '', den_text).strip()
            math_fn = {'log', 'sen', 'cos', 'tg', 'rad', 'det', 'max', 'min', 'lim'}
            words_num = [w for w in re.findall(r'[a-zA-ZÀ-ÿ]{3,}', clean_num) if w.lower() not in math_fn]
            words_den = [w for w in re.findall(r'[a-zA-ZÀ-ÿ]{3,}', clean_den) if w.lower() not in math_fn]

            if words_num or words_den or len(num_text) > 35 or len(den_text) > 35:
                continue

            for s in num_spans: s["used"] = True
            for s in den_spans: s["used"] = True
            for c in num_comp: c["used"] = True
            for c in den_comp: c["used"] = True

            min_x = min(x0, all_num[0]['bbox'][0], all_den[0]['bbox'][0])
            max_x = max(x1, all_num[-1]['bbox'][2], all_den[-1]['bbox'][2])
            min_y = min(item['bbox'][1] for item in all_num)
            max_y = max(item['bbox'][3] for item in all_den)

            composite_elements.append({
                "text": f"\\frac{{{num_text}}}{{{den_text}}}",
                "bbox": [min_x, min_y, max_x, max_y],
                "origin": [min_x, y],
                "size": max(item["size"] for item in all_num + all_den),
                "is_math": True
            })

    # 3. Reconstrução de Matrizes (\begin{pmatrix} ... \end{pmatrix})
    lb_spans = [s for s in spans if not s["used"] and s["is_lb"]]
    rb_spans = [s for s in spans if not s["used"] and s["is_rb"]]

    lb_groups = []
    for s in sorted(lb_spans, key=lambda s: (s['bbox'][0], s['bbox'][1])):
        if not lb_groups or abs(s['bbox'][0] - lb_groups[-1][-1]['bbox'][0]) > 5 or abs(s['bbox'][1] - lb_groups[-1][-1]['bbox'][3]) > 10:
            lb_groups.append([s])
        else:
            lb_groups[-1].append(s)

    rb_groups = []
    for s in sorted(rb_spans, key=lambda s: (s['bbox'][0], s['bbox'][1])):
        if not rb_groups or abs(s['bbox'][0] - rb_groups[-1][-1]['bbox'][0]) > 5 or abs(s['bbox'][1] - rb_groups[-1][-1]['bbox'][3]) > 10:
            rb_groups.append([s])
        else:
            rb_groups[-1].append(s)

    for lg in lb_groups:
        ly0 = min(s['bbox'][1] for s in lg)
        ly1 = max(s['bbox'][3] for s in lg)
        lx1 = max(s['bbox'][2] for s in lg)
        matching_rg = [
            rg for rg in rb_groups
            if abs(min(s['bbox'][1] for s in rg) - ly0) < 10
            and abs(max(s['bbox'][3] for s in rg) - ly1) < 10
            and min(s['bbox'][0] for s in rg) > lx1
        ]
        if matching_rg:
            rg = matching_rg[0]
            rx0 = min(s['bbox'][0] for s in rg)
            matrix_spans = [
                s for s in spans if not s["used"]
                and lx1 - 2 <= s['bbox'][0] and s['bbox'][2] <= rx0 + 2
                and ly0 - 4 <= s['bbox'][1] and s['bbox'][3] <= ly1 + 4
                and s not in lg and s not in rg
            ]
            if matrix_spans:
                for s in lg + rg + matrix_spans:
                    s["used"] = True
                rows = []
                for s in sorted(matrix_spans, key=lambda s: s['bbox'][1]):
                    y_mid = (s['bbox'][1] + s['bbox'][3]) / 2.0
                    if not rows or abs(y_mid - rows[-1][0]) > 6.0:
                        rows.append((y_mid, [s]))
                    else:
                        rows[-1][1].append(s)
                row_strs = []
                for y_mid, r_spans in rows:
                    r_spans.sort(key=lambda s: s['bbox'][0])
                    row_strs.append(' & '.join(t for t in (s['text'].strip() for s in r_spans) if t))
                mat_latex = r'\begin{pmatrix} ' + ' \\\\ '.join(row_strs) + r' \end{pmatrix}'
                composite_elements.append({
                    "text": mat_latex,
                    "bbox": [min(s['bbox'][0] for s in lg), ly0, max(s['bbox'][2] for s in rg), ly1],
                    "origin": [min(s['bbox'][0] for s in lg), ly1],
                    "size": max(s["size"] for s in matrix_spans),
                    "is_math": True
                })

    # 4. Agrupamento em linhas e formatação final
    remaining = [s for s in spans if not s["used"]]
    remaining += [c for c in composite_elements if not c.get("used")]

    if not remaining:
        return ""

    # Identifica itens da linha base (tamanho de texto padrão >= 8.0)
    base_items = [it for it in remaining if it["size"] >= 8.0]
    if not base_items:
        base_items = remaining

    base_lines = []
    for it in sorted(base_items, key=lambda it: (it["bbox"][1] + it["bbox"][3]) / 2.0):
        y_mid = (it["bbox"][1] + it["bbox"][3]) / 2.0
        if not base_lines or abs(y_mid - base_lines[-1]["y_mid"]) > 9.0:
            base_lines.append({
                "y_mid": y_mid,
                "y0": it["bbox"][1],
                "y1": it["bbox"][3],
                "items": [it]
            })
        else:
            bl = base_lines[-1]
            bl["items"].append(it)
            bl["y0"] = min(bl["y0"], it["bbox"][1])
            bl["y1"] = max(bl["y1"], it["bbox"][3])
            bl["y_mid"] = (bl["y0"] + bl["y1"]) / 2.0

    non_base = [it for it in remaining if it not in base_items]
    for it in non_base:
        it_y_mid = (it["bbox"][1] + it["bbox"][3]) / 2.0
        closest_bl = min(base_lines, key=lambda bl: abs(it_y_mid - bl["y_mid"]))
        closest_bl["items"].append(it)

    formatted_lines = []
    for bl in base_lines:
        line = bl["items"]
        line.sort(key=lambda item: item["bbox"][0])
        base_size = max(item["size"] for item in line)
        base_items_in_line = [item for item in line if item["size"] >= base_size * 0.85]
        base_orig_y = base_items_in_line[0]["origin"][1] if base_items_in_line else line[0]["origin"][1]

        line_tokens = []
        for item in line:
            t = item["text"]
            if item["size"] < base_size * 0.85:
                if item["origin"][1] > base_orig_y + 1.2:
                    t = f"_{{{t}}}"
                elif item["origin"][1] < base_orig_y - 1.2 or (item.get("is_math") and item["bbox"][3] <= base_orig_y):
                    t = f"^{{{t}}}"
            line_tokens.append((t, item))

        res_str = ""
        prev_item = None
        for t, item in line_tokens:
            if prev_item:
                gap = item["bbox"][0] - prev_item["bbox"][2]
                if gap > 2.0 and not res_str.endswith(" ") and not t.startswith((" ", "^", "_")):
                    res_str += " "
            res_str += t
            prev_item = item

        brace_pat = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        for _ in range(3):
            res_str = re.sub(r'\^(' + brace_pat + r')\s*\^(' + brace_pat + r')', lambda m: f"^{{{m.group(1)[1:-1].strip()} {m.group(2)[1:-1].strip()}}}", res_str)
            res_str = re.sub(r'_(' + brace_pat + r')\s*_(' + brace_pat + r')', lambda m: f"_{{{m.group(1)[1:-1].strip()} {m.group(2)[1:-1].strip()}}}", res_str)
        res_str = re.sub(r'\^\{([^}]+)\s+-\s*(\d+)\}', r'^{\1 - \2}', res_str)

        # Colapsa múltiplos parênteses de blocos escaláveis (InDesign) em \left( e \right)
        res_str = re.sub(r'\({2,}', lambda m: r'\left(', res_str)
        res_str = re.sub(r'\){2,}', lambda m: r'\right)', res_str)

        # Remove duplicatas de letras de alternativa consecutivas: 'A A' -> 'A'
        res_str = re.sub(r'^([A-E])\s+\1(?:\s+|$)', r'\1 ', res_str.strip())

        m_alt = re.match(r'^([A-E])\s+(.*)$', res_str.strip())
        if m_alt:
            alt_let = m_alt.group(1)
            alt_body = m_alt.group(2).strip()
            # Se a alternativa contém símbolos matemáticos, envolve em $ ... $
            if any(sym in alt_body for sym in [r'\frac', r'\sqrt', r'\pi', r'\cdot', r'\times', r'\begin{pmatrix}', '^', '_', '=']):
                if not alt_body.startswith('$'):
                    alt_body = f"${alt_body}$"
            res_str = f"{alt_let} {alt_body}"
        elif any(sym in res_str for sym in [r'\frac', r'\sqrt', r'\begin{pmatrix}']):
            clean_text = re.sub(r'\\[a-zA-Z]+', '', res_str)
            prose_words = [w for w in re.findall(r'\b[a-zA-ZÀ-ÿ]{3,}\b', clean_text)]
            if len(prose_words) >= 2:
                # Linha de prosa contendo fórmula inline: envolve apenas as fórmulas matemáticas em $ ... $
                res_str = re.sub(r'(\d+\s+)?(\\frac\{[^{}]+\}\{[^{}]+\})', r'$\g<0>$', res_str)
                res_str = re.sub(r'(\\sqrt(?:\[[^\]]+\])?\{[^{}]+\})', r'$\g<0>$', res_str)
            else:
                # Linha de equação matemática pura: envolve a linha inteira em $ ... $
                if not res_str.strip().startswith('$'):
                    res_str = f"${res_str.strip()}$"

        formatted_lines.append(res_str.strip())

    return "\n".join(l for l in formatted_lines if l)

def detect_page_column_rects(page: pymupdf.Page) -> List[pymupdf.Rect]:
    """
    Detecta automaticamente se a página utiliza layout de coluna única (largura total)
    ou layout de duas colunas, evitando cortes indevidos em tabelas e fórmulas centralizadas.
    """
    mid_x = page.rect.width / 2.0
    crossing = [
        b for b in page.get_text('blocks')
        if b[0] < mid_x - 40 and b[2] > mid_x + 40 and b[1] > 50 and b[3] < 740 and (b[2] - b[0]) > 280
    ]
    if len(crossing) >= 2:
        return [pymupdf.Rect(0, 0, page.rect.width, page.rect.height)]
    else:
        return [
            pymupdf.Rect(0, 0, mid_x, page.rect.height),
            pymupdf.Rect(mid_x, 0, page.rect.width, page.rect.height)
        ]

def extract_page_column_text(page: pymupdf.Page) -> str:
    """
    Extrai o texto da página respeitando a geometria das colunas e reconstruindo
    fórmulas matemáticas em formato LaTeX padronizado.
    """
    column_rects = detect_page_column_rects(page)
    col_texts = []
    for rect in column_rects:
        raw_col = extract_column_math_text(page, rect)
        col_texts.append(clean_page_text(raw_col))
    return "\n".join(col_texts)


def extract_vector_circle_alternatives(doc: pymupdf.Document) -> Dict[int, Dict[str, str]]:
    """
    Detecta alternativas representadas como desenhos vetoriais circulares (ex.: ENEM 2010 Regular),
    correlacionando cada questão com seus 5 círculos vetoriais e capturando o texto associado.
    """
    circles_per_q = {}
    for pno in range(1, len(doc)):
        page = doc[pno]
        mid_x = page.rect.width / 2.0
        blocks = page.get_text("blocks")
        q_headers = []
        for b in blocks:
            m = re.search(r'Quest[ãa]o\s+(\d+)', b[4], re.I)
            if m:
                col = 0 if b[0] < mid_x else 1
                q_headers.append((int(m.group(1)), col, b[1]))
        q_headers.sort(key=lambda x: (x[1], x[2]))

        circles = []
        for d in page.get_drawings():
            r = d['rect']
            w = r[2] - r[0]
            h = r[3] - r[1]
            if 6.8 <= w <= 7.0 and 6.8 <= h <= 7.0 and len(d.get('items', [])) == 4 and d.get('fill') is not None and d.get('fill')[0] < 0.2:
                col = 0 if r[0] < mid_x else 1
                circles.append((col, r[1], r))
        circles.sort(key=lambda x: (x[0], x[1]))

        if len(circles) == len(q_headers) * 5 and len(circles) > 0:
            lines = []
            for b in page.get_text("dict")["blocks"]:
                if "lines" in b:
                    for l in b["lines"]:
                        lt = "".join(s["text"] for s in l["spans"]).strip()
                        if lt:
                            lines.append((l["bbox"], lt))
            for q_idx, (q_num, q_col, q_y) in enumerate(q_headers):
                q_circs = [c[2] for c in circles[q_idx * 5 : (q_idx + 1) * 5]]
                x_min = min(c[0] for c in q_circs)
                sub_left = [c for c in q_circs if c[0] < x_min + 50]
                sub_right = [c for c in q_circs if c[0] >= x_min + 50]
                sub_left.sort(key=lambda c: c[1])
                sub_right.sort(key=lambda c: c[1])
                if len(sub_left) == 3 and len(sub_right) == 2:
                    ordered = sub_left + sub_right
                else:
                    ordered = sorted(q_circs, key=lambda c: c[1])
                alts = {}
                for let, c in zip("ABCDE", ordered):
                    matched = [l[1] for l in lines if abs(l[0][1] - c[1]) < 8 and c[2] - 5 < l[0][0] < c[2] + 250]
                    c_text = " ".join(matched).strip()
                    c_text = ALT_FOOTER_CLEANUP_REGEX.sub("", c_text).strip()
                    c_text = BARCODE_REGEX.sub("", c_text).strip()
                    c_text = re.sub(r'\bRascunho\b.*$', '', c_text, flags=re.I).strip()
                    if not c_text or c_text.startswith("xxxx"):
                        c_text = IMAGE_ALT_PLACEHOLDER
                    alts[let] = c_text
                circles_per_q[q_num] = alts
    return circles_per_q

def extract_questions_from_pdf(pdf_path: Path) -> Dict[Tuple[int, Optional[float]], Dict[str, Any]]:
    """
    Extrai todas as questões de um caderno PDF, retornando um dicionário indexado por (número_questão, língua).
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    doc = pymupdf.open(pdf_path)
    doc = repair_pdf_document_fonts(doc)

    # Extrai e limpa o texto das páginas respeitando as duas colunas
    pages_text = []
    for p in range(1, len(doc)):
        page = doc[p]
        raw_full_page = page.get_text()
        has_quest = bool(QUESTION_SPLIT_REGEX.search(raw_full_page))
        if not has_quest:
            upper_raw = raw_full_page.upper()
            # Descarta Folha de Rascunho da Redação
            if "RASCUNHO" in upper_raw and any(k in upper_raw for k in ["REDAÇÃO", "REDACAO", "FOLHA DE REDAÇÃO", "TRANSCREVA"]):
                continue
            # Descarta contracapa de fechamento na última página do caderno
            if p == len(doc) - 1:
                continue
        pages_text.append(extract_page_column_text(page))
    full_text = "\n".join(pages_text)

    # Detecta previamente alternativas representadas por desenhos vetoriais (ex: 2010 Regular)
    vector_circle_alts = extract_vector_circle_alternatives(doc)

    # Verifica se há ocorrência múltipla das Questões 1 e 2 (indicador real de Inglês/Espanhol)
    q1_count = len(re.findall(r'(?:^|\n)\s*QUEST[ÃA]O\s+1(?:\D|$)', full_text, flags=re.IGNORECASE))
    q2_count = len(re.findall(r'(?:^|\n)\s*QUEST[ÃA]O\s+2(?:\D|$)', full_text, flags=re.IGNORECASE))
    has_duplicate_languages = (q1_count >= 2 and q2_count >= 2)

    # Detecta imagens nas questões
    questions_with_spatial_images = detect_images_per_question(doc, has_duplicate_languages)

    splits = QUESTION_SPLIT_REGEX.split(full_text)
    parsed_questions: Dict[Tuple[int, Optional[float]], Dict[str, Any]] = {}
    seen_1 = 0

    for i in range(1, len(splits), 2):
        q_num = int(splits[i])
        q_text = splits[i + 1]

        # Resolução de língua estrangeira quando há duplicata real
        lang = None
        if has_duplicate_languages:
            if q_num == 1:
                seen_1 += 1
            if q_num <= 5:
                lang = 0.0 if seen_1 == 1 else 1.0

        enunciado, alts = parse_question_body(q_text)

        # Se não encontrou alternativas no texto, verifica alternativas vetoriais pré-extraídas
        if not alts and q_num in vector_circle_alts:
            alts = vector_circle_alts[q_num]
            first_alt = alts.get('A', '')
            if first_alt and first_alt != IMAGE_ALT_PLACEHOLDER:
                pos_alt = enunciado.find(first_alt)
                if pos_alt > 0:
                    enunciado = sanitize_question_text(enunciado[:pos_alt])

        # Determina se a questão contém imagem
        has_img_in_alts = any(val == IMAGE_ALT_PLACEHOLDER for val in alts.values())
        has_spatial_img = (q_num, lang) in questions_with_spatial_images

        # Fallback para questões puramente gráficas/visuais sem alternativas em texto legível
        if not alts or len(alts) < 5:
            alts = {let: IMAGE_ALT_PLACEHOLDER for let in 'ABCDE'}
            has_img_in_alts = True
            # Limpa possíveis resíduos de letras de alternativas no fim do enunciado
            enunciado = re.sub(r'(?:[\s\n]*[A-E]\b[\s\n]*){3,10}(?:2ª\s*aplicação)?\s*$', '', enunciado, flags=re.I).strip()
            enunciado = sanitize_question_text(enunciado)

        has_image = 1 if (has_img_in_alts or has_spatial_img) else 0

        key = (q_num, lang)
        parsed_questions[key] = {
            'CO_POSICAO': q_num,
            'TP_LINGUA': lang,
            'DESC_ENUNCIADO': enunciado,
            'DESC_ALTER_A': alts.get('A', ''),
            'DESC_ALTER_B': alts.get('B', ''),
            'DESC_ALTER_C': alts.get('C', ''),
            'DESC_ALTER_D': alts.get('D', ''),
            'DESC_ALTER_E': alts.get('E', ''),
            'IN_ITEM_IMAGEM': has_image,
            'REF_ARQUIVO_PDF': pdf_path.name
        }

    return parsed_questions
