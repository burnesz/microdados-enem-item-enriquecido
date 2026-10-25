"""
Módulo para extração de texto, enunciados, alternativas e detecção de imagens dos PDFs do ENEM.
"""

from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
import re
import unicodedata
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
    IMAGE_ALT_PLACEHOLDER,
    EXPLICIT_IMAGE_REGEX,
    EXPLICIT_TABLE_REGEX
)
from src.table_extractor import PageTable, extract_page_tables

# Marcador provisório de tabela estruturada no fluxo de texto (página.índice), substituído pelo Markdown
TABLE_PLACEHOLDER = '⟦TABELA:{}.{}⟧'
TABLE_PLACEHOLDER_REGEX = re.compile(r'\s*⟦TABELA:(\d+)\.(\d+)⟧\s*')

# Ordem de glifos das fontes Arial (TrueType): a ordem padrão do Macintosh (índices 0-257 da tabela
# 'post') sem 'nonbreakingspace' (172) e 'apple' (210), que a Arial não possui. Nomes InDesign /g<N> e
# CIDs com CIDToGIDMap Identity referem-se a esses índices. Validado pelas larguras das fontes do corpus
# (ex.: 112 'é' 556, 131 '°' 400, 168 'Δ' 612, 178 '—' 1000, 200 'Á' 722 em negrito, 237 '−' 584).
_MAC_ORDER_HIGH = (
    'ÄÅÇÉÑÖÜáàâäãåçéèêëíìîïñóòôöõúùûü†°¢£§•¶ß®©™´¨≠ÆØ∞±≤≥¥µ∂∑∏π∫ªºΩæø¿¡¬√ƒ≈Δ«»…\x00ÀÃÕŒœ–—“”‘’÷◊ÿŸ⁄¤‹›'
    '\x01\x02‡·‚„‰ÂÊÁËÈÍÎÏÌÓÔ\x00ÒÚÛÙıˆ˜¯˘˙˚¸˝˛ˇŁłŠšŽž¦ÐðÝýÞþ-×¹²³½¼¾₣ĞğİŞşĆćČčđ'
)
ARIAL_GLYPH_CHARS: List[str] = [''] * 3 + [chr(i + 29) for i in range(3, 98)] + [
    {'\x01': 'fi', '\x02': 'fl'}.get(c, c) for c in _MAC_ORDER_HIGH if c != '\x00'
]

# Letras e dígitos do bloco alfanumérico matemático (ex.: 𝜋 itálico da Cambria Math), que a fonte
# repete com um segundo glifo de largura zero; viram o caractere comum (π)
MATH_ALNUM_REGEX = re.compile(r'([\U0001D400-\U0001D7FF])\1?')

# Espaço fino (largura 83/1000) entre letra e índice: removido na montagem do texto, pois o
# espaçamento real já vem da posição dos glifos
HAIR_SPACE = '\u200a'

# Glifos além da ordem padrão (índice >= 256) nas fontes Arial, por estilo (os índices altos diferem
# entre estilos). Identificados visualmente nos cadernos e conferidos pela largura declarada, pois os
# subconjuntos embutidos não trazem tabelas 'post'/'cmap' com nomes. Ex.: ArialMT 314 '→' (largura
# 1000, em 2010 e 2021), 400 'ℓ' (2010), 3437 '2' sobrescrito em m⁻² (556), 3675-3680 Q₁…Q₆ (2023);
# Arial-ItalicMT 2288 espaço fino (83, em 2021 e 2023), 2577 a variável I (2023 Q163).
ARIAL_HIGH_GLYPHS: Dict[str, Dict[int, str]] = {
    'ArialMT': {
        307: 'φ', 314: '→', 326: '–', 400: 'ℓ', 540: 'λ', 652: 'π', 3433: '8', 3437: '2', 3438: '3',
        3675: '₁', 3676: '₂', 3677: '₃', 3678: '₄', 3679: '₅', 3680: '₆',
    },
    'Arial-ItalicMT': {408: 'Ĉ', 975: 'ℰ', 2288: HAIR_SPACE, 2476: 'ℰ', 2577: 'I'},
    'Arial-BoldMT': {3032: HAIR_SPACE},
}

# Cambria Math (itálico matemático do Word), mesma identificação visual + largura; os índices
# 3397 '+' e 3398 '−' repetem-se em 2021 P1 e P2 com o mesmo glifo. Também completa os /ToUnicode
# que apontam glifos para U+FFFD (2011 P1: 3 espaço, 1857 'e', 3404 '=', 3493 '√').
CAMBRIA_MATH_GLYPHS: Dict[int, str] = {
    3: ' ', 521: '⋅', 543: 'Δ', 882: '0', 885: '3', 1488: '∈', 1828: 'B', 1857: 'e', 1859: 'g', 2029: 'v',
    3397: '+', 3398: '-', 3404: '=', 3493: '√',
}

# Nomes de glifo corrompidos no próprio PDF de origem (';#2323...'), por subconjunto de fonte
# (o prefixo é único de cada arquivo), identificados visualmente.
SOURCE_GLYPH_FIXES: Dict[str, Dict[int, str]] = {
    'HNLNDB+ArialMT': {0xA3: '2', 0xA4: '3'},  # ENEM 2010 PPL: a fração 2/3
}

def font_style(base_font: str) -> str:
    """Nome da fonte sem prefixo de subconjunto nem sufixo de codificação (ex.: 'ArialMT')."""
    return re.sub(r'-Identity-H$', '', base_font.split('+')[-1])

def arial_glyph_to_unicode(gname: str, base_font: str = '') -> Optional[str]:
    """Nome InDesign /g<N> em fonte Arial -> caractere pela ordem de glifos da Arial."""
    m = re.fullmatch(r'g(\d+)', gname)
    if m:
        n = int(m.group(1))
        if 3 <= n < len(ARIAL_GLYPH_CHARS):
            return ARIAL_GLYPH_CHARS[n]
        high = ARIAL_HIGH_GLYPHS.get(font_style(base_font), {})
        if n in high:
            return high[n]
    return glyph_to_unicode(gname)

def build_indesign_identity_h_cmap(extra: Optional[Dict[int, str]] = None, arial: bool = False) -> str:
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
    if arial:
        # Fontes Arial: CIDs 3-255 pela ordem de glifos da Arial (substitui os palpites acima nessa faixa)
        extra_cids.update({cid: ch for cid, ch in enumerate(ARIAL_GLYPH_CHARS) if ch})
    extra_cids.update(extra or {})
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

# Codificação Adobe Symbol (código do caractere -> Unicode). O sinal de menos é mantido como '-' ASCII,
# como no restante da pipeline; peças de colchetes/chaves escaláveis viram o delimitador simples.
SYMBOL_ENCODING_UNICODE: Dict[int, str] = {
    0x20: ' ', 0x21: '!', 0x22: '∀', 0x23: '#', 0x24: '∃', 0x25: '%', 0x26: '&', 0x27: '∋',
    0x28: '(', 0x29: ')', 0x2A: '*', 0x2B: '+', 0x2C: ',', 0x2D: '-', 0x2E: '.', 0x2F: '/',
    0x3A: ':', 0x3B: ';', 0x3C: '<', 0x3D: '=', 0x3E: '>', 0x3F: '?', 0x40: '≅',
    0x41: 'Α', 0x42: 'Β', 0x43: 'Χ', 0x44: 'Δ', 0x45: 'Ε', 0x46: 'Φ', 0x47: 'Γ', 0x48: 'Η',
    0x49: 'Ι', 0x4A: 'ϑ', 0x4B: 'Κ', 0x4C: 'Λ', 0x4D: 'Μ', 0x4E: 'Ν', 0x4F: 'Ο', 0x50: 'Π',
    0x51: 'Θ', 0x52: 'Ρ', 0x53: 'Σ', 0x54: 'Τ', 0x55: 'Υ', 0x56: 'ς', 0x57: 'Ω', 0x58: 'Ξ',
    0x59: 'Ψ', 0x5A: 'Ζ', 0x5B: '[', 0x5C: '∴', 0x5D: ']', 0x5E: '⊥', 0x5F: '_',
    0x61: 'α', 0x62: 'β', 0x63: 'χ', 0x64: 'δ', 0x65: 'ε', 0x66: 'φ', 0x67: 'γ', 0x68: 'η',
    0x69: 'ι', 0x6A: 'ϕ', 0x6B: 'κ', 0x6C: 'λ', 0x6D: 'μ', 0x6E: 'ν', 0x6F: 'ο', 0x70: 'π',
    0x71: 'θ', 0x72: 'ρ', 0x73: 'σ', 0x74: 'τ', 0x75: 'υ', 0x76: 'ϖ', 0x77: 'ω', 0x78: 'ξ',
    0x79: 'ψ', 0x7A: 'ζ', 0x7B: '{', 0x7C: '|', 0x7D: '}', 0x7E: '∼',
    0xA1: 'ϒ', 0xA2: '′', 0xA3: '≤', 0xA4: '⁄', 0xA5: '∞', 0xA6: 'ƒ', 0xA7: '♣', 0xA8: '♦',
    0xA9: '♥', 0xAA: '♠', 0xAB: '↔', 0xAC: '←', 0xAD: '↑', 0xAE: '→', 0xAF: '↓', 0xB0: '°',
    0xB1: '±', 0xB2: '″', 0xB3: '≥', 0xB4: '×', 0xB5: '∝', 0xB6: '∂', 0xB7: '•', 0xB8: '÷',
    0xB9: '≠', 0xBA: '≡', 0xBB: '≈', 0xBC: '…', 0xBF: '↵', 0xC0: 'ℵ', 0xC1: 'ℑ', 0xC2: 'ℜ',
    0xC3: '℘', 0xC4: '⊗', 0xC5: '⊕', 0xC6: '∅', 0xC7: '∩', 0xC8: '∪', 0xC9: '⊃', 0xCA: '⊇',
    0xCB: '⊄', 0xCC: '⊂', 0xCD: '⊆', 0xCE: '∈', 0xCF: '∉', 0xD0: '∠', 0xD1: '∇', 0xD2: '®',
    0xD3: '©', 0xD4: '™', 0xD5: '∏', 0xD6: '√', 0xD7: '⋅', 0xD8: '¬', 0xD9: '∧', 0xDA: '∨',
    0xDB: '⇔', 0xDC: '⇐', 0xDD: '⇑', 0xDE: '⇒', 0xDF: '⇓', 0xE0: '◊', 0xE1: '〈', 0xE5: '∑',
    0xE6: '(', 0xE7: '(', 0xE8: '(', 0xE9: '[', 0xEA: '[', 0xEB: '[', 0xEC: '{', 0xED: '{',
    0xEE: '{', 0xF1: '〉', 0xF2: '∫', 0xF6: ')', 0xF7: ')', 0xF8: ')', 0xF9: ']', 0xFA: ']',
    0xFB: ']', 0xFC: '}', 0xFD: '}', 0xFE: '}',
}
for _n in range(10):
    SYMBOL_ENCODING_UNICODE[0x30 + _n] = str(_n)

def build_symbol_cmap() -> str:
    """
    Constrói um CMap /ToUnicode para fontes Symbol e SymbolMT Type0 /Identity-H.
    Nessas fontes o CID é o índice do glifo na SymbolMT: CID = código - 29 na faixa ASCII
    (0x20..0x7E) e CID = código - 63 na faixa alta (0xA1..0xFE). A convenção foi validada
    pelas larguras /W de todas as fontes do corpus (ex.: CID 14 '+', 31 '<', 32 '=', 100 '≤',
    117 '×' com 549; CID 3 espaço com 250; CID 143 '∈' com 713).
    """
    symbol_map = {}
    for code, ch in SYMBOL_ENCODING_UNICODE.items():
        cid = code - 29 if code <= 0x7E else code - 63
        symbol_map[cid] = ch

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
    '⋅': r'\cdot', '×': r'\times', '≤': r'\le', '≥': r'\ge', '≠': r'\ne', '≈': r'\approx', '±': r'\pm',
    # Caracteres Unicode produzidos pelo CMap de build_symbol_cmap
    'γ': r'\gamma', 'δ': r'\delta', 'ε': r'\varepsilon', 'λ': r'\lambda', 'μ': r'\mu', 'ν': r'\nu',
    'ρ': r'\rho', 'σ': r'\sigma', 'τ': r'\tau', 'φ': r'\varphi', 'ω': r'\omega',
    'Δ': r'\Delta', 'Π': r'\Pi', 'Ω': r'\Omega',
    '•': r'\cdot', '∞': r'\infty', '∅': r'\varnothing', '∈': r'\in', '∉': r'\notin',
    '≡': r'\equiv', '÷': r'\div', '°': r'^\circ', '∂': r'\partial', '∑': r'\sum',
    '∩': r'\cap', '∪': r'\cup', '⊂': r'\subset', '⊃': r'\supset',
    'υ': r'\upsilon', '≅': r'\cong', '→': r'\rightarrow', '⇒': r'\Rightarrow'
}

# Mapeamento de caracteres matemáticos Unicode em texto padrão para LaTeX
UNICODE_MATH_MAP: Dict[str, str] = {
    '²': '^2', '³': '^3', '¹': '^1', '⁰': '^0', '⁴': '^4', '⁵': '^5',
    '⁶': '^6', '⁷': '^7', '⁸': '^8', '⁹': '^9', 'ⁿ': '^n',
    '₀': '_0', '₁': '_1', '₂': '_2', '₃': '_3', '₄': '_4',
    '₅': '_5', '₆': '_6', '₇': '_7', '₈': '_8', '₉': '_9',
    'π': r'\pi', 'Σ': r'\pi', '×': r'\times', '÷': r'\div', '±': r'\pm',
    '≤': r'\le', '≥': r'\ge', '≠': r'\ne', '≈': r'\approx',
    '•': r'\bullet', '°': r'^\circ', '⋅': r'\cdot', '√': r'\sqrt', 'ℝ': r'\mathbb{R}'
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

def symbol_glyph_to_unicode(gname: str) -> Optional[str]:
    """
    Nomes InDesign /g<N> em fontes SymbolMT referem-se ao índice do glifo na SymbolMT original,
    na mesma convenção de build_symbol_cmap (N + 29 na faixa ASCII, N + 63 na faixa alta).
    Validado pelas larguras /Widths das fontes do corpus (ex.: g100 '≤' 549, g113 '°' 400,
    g143 '∈' 713, g95 '|' 200). Nomes padrão (ex.: 'plus') seguem glyph_to_unicode.
    """
    if re.fullmatch(r'g\d+', gname):
        n = int(gname[1:])
        return SYMBOL_ENCODING_UNICODE.get(n + 29 if n <= 97 else n + 63)
    return glyph_to_unicode(gname)

def build_tounicode_from_differences(enc_str: str, font_name: str = '') -> Optional[str]:
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
            gnum = re.fullmatch(r'g(\d+)', gname)
            if 'Symbol' in font_name:
                u = symbol_glyph_to_unicode(gname)
            elif 'Arial' in font_name:
                u = arial_glyph_to_unicode(gname, font_name)
            elif 'CambriaMath' in font_name and gnum and int(gnum.group(1)) in CAMBRIA_MATH_GLYPHS:
                u = CAMBRIA_MATH_GLYPHS[int(gnum.group(1))]
            else:
                u = glyph_to_unicode(gname)
            if u:
                code_to_uni[curr_code] = u
            curr_code += 1
    code_to_uni.update(SOURCE_GLYPH_FIXES.get(font_name, {}))
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

# Área de uso privado da Adobe com peças de delimitadores escaláveis (fontes Symbol). A peça
# extensora fica na linha da fórmula e vira o delimitador; topo e base ficam nas linhas vizinhas
# e viram espaço (senão sobram soltas acima e abaixo da expressão).
ADOBE_PUA_PIECES: Dict[int, str] = {cp: ' ' for cp in range(0xF8E5, 0xF8FF)}
ADOBE_PUA_PIECES.update({
    0xF8EC: '(', 0xF8F7: ')', 0xF8EF: '[', 0xF8FA: ']', 0xF8F2: '{', 0xF8FD: '}',
    0xF8E8: '®', 0xF8E9: '©', 0xF8EA: '™',
})

# MT Extra (MathType), glifos identificados visualmente nos cadernos. Os acentos (seta de vetor
# sobre F, chapéu de ângulo sobre PRQ) não têm posição representável em texto linear: viram espaço.
MT_EXTRA_PUA: Dict[int, str] = {0xF0A1: 'ℝ', 0xF072: ' ', 0xF0B5: ' '}

def remap_private_use(cp: int, base_font: str) -> Optional[str]:
    """
    Converte um ponto de código da área de uso privado produzido pelo /ToUnicode de fontes
    simbólicas no caractere real. Fontes da família Symbol usam a convenção Windows
    U+F000 + código na codificação Symbol (ex.: U+F02B '+', U+F0DE '⇒').
    """
    if 'Symbol' in base_font:
        if 0xF020 <= cp <= 0xF0FF:
            return SYMBOL_ENCODING_UNICODE.get(cp - 0xF000)
        return ADOBE_PUA_PIECES.get(cp)
    if 'MT-Extra' in base_font or 'MTExtra' in base_font:
        return MT_EXTRA_PUA.get(cp)
    return None

def remap_tounicode_private_use(cmap: str, base_font: str) -> Optional[str]:
    """
    Reescreve um /ToUnicode existente substituindo destinos na área de uso privado
    (remap_private_use) e, na Cambria Math, destinos U+FFFD pelo glifo (CAMBRIA_MATH_GLYPHS).
    Retorna o novo CMap, ou None se nada mudou.
    """

    def utf16(h: str) -> str:
        return bytes.fromhex(h).decode('utf-16-be', errors='replace') if h else ''

    mapping: Dict[str, str] = {}
    for block in re.findall(r'beginbfchar(.*?)endbfchar', cmap, re.S):
        for src, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>', block):
            mapping[src.upper()] = utf16(dst)
    for block in re.findall(r'beginbfrange(.*?)endbfrange', cmap, re.S):
        for lo, hi, dst in re.findall(r'<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(\[[^\]]*\]|<[0-9A-Fa-f]*>)', block):
            a, b, width = int(lo, 16), int(hi, 16), len(lo)
            if dst.startswith('['):
                for i, d in enumerate(re.findall(r'<([0-9A-Fa-f]*)>', dst)):
                    mapping[f'{a + i:0{width}X}'] = utf16(d)
            else:
                base = dst[1:-1]
                for i in range(b - a + 1):
                    mapping[f'{a + i:0{width}X}'] = utf16(f'{int(base, 16) + i:0{len(base)}X}')

    changed = False
    for src, dst in mapping.items():
        new = remap_private_use(ord(dst), base_font) if len(dst) == 1 and 0xE000 <= ord(dst) <= 0xF8FF else None
        if dst == '\ufffd' and 'CambriaMath' in base_font:
            new = CAMBRIA_MATH_GLYPHS.get(int(src, 16))
        if new:
            mapping[src] = new
            changed = True
    if not changed:
        return None

    codespace = re.search(r'\d+\s+begincodespacerange.*?endcodespacerange', cmap, re.S)
    lines = [
        '/CIDInit /ProcSet findresource begin',
        '12 dict begin',
        'begincmap',
        '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
        '/CMapName /Custom-PUA-Remap def',
        '/CMapType 2 def',
        codespace.group(0) if codespace else '1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange',
    ]
    items = [(s, d) for s, d in sorted(mapping.items()) if d]
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        lines.append(f'{len(chunk)} beginbfchar')
        for src, dst in chunk:
            lines.append(f'<{src}> <{dst.encode("utf-16-be").hex().upper()}>')
        lines.append('endbfchar')
    lines.extend(['endcmap', 'CMapName currentdict /CMap defineresource pop', 'end', 'end'])
    return '\n'.join(lines)

def repair_pdf_document_fonts(doc: pymupdf.Document) -> pymupdf.Document:
    """
    Inspeciona o documento PDF em busca de:
    1. Fontes Type0 /Identity-H que não possuem a tabela /ToUnicode CMap.
    2. Fontes Type1 com dicionário /Encoding contendo vetor /Differences com glifos
       InDesign (/g<CID>) que foram omitidos ou truncados no /ToUnicode original.
    3. Fontes simbólicas (Symbol, MT Extra) cujo /ToUnicode aponta para a área de uso privado.
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
                    bf = re.search(r'/BaseFont\s*/(\S+)', obj)
                    style = font_style(bf.group(1)) if bf else ''
                    if 'Calibri' in obj:
                        cmap_bytes = calibri_bytes
                    elif 'Symbol' in obj:
                        cmap_bytes = symbol_bytes
                    elif 'Arial' in style:
                        cmap_bytes = build_indesign_identity_h_cmap(ARIAL_HIGH_GLYPHS.get(style), arial=True).encode('ascii')
                    else:
                        cmap_bytes = indesign_bytes
                    cmap_xref = doc.get_new_xref()
                    doc.update_object(cmap_xref, f'<< /Length {len(cmap_bytes)} >>\nstream\n')
                    doc.update_stream(cmap_xref, cmap_bytes)
                    doc.xref_set_key(xref, 'ToUnicode', f'{cmap_xref} 0 R')
                    modified = True

                # 2. Type1 com /Differences contendo glifos InDesign /g<CID>
                differences_cmap = False
                m = re.search(r'/Encoding\s+(\d+)\s+0\s+R', obj)
                enc_str = doc.xref_object(int(m.group(1))) if m else obj
                if '/Differences' in enc_str and '/g' in enc_str:
                    bf = re.search(r'/BaseFont\s*/(\S+)', obj)
                    cmap_str = build_tounicode_from_differences(enc_str, bf.group(1) if bf else '')
                    if cmap_str:
                        cmap_bytes = cmap_str.encode('ascii')
                        cmap_xref = doc.get_new_xref()
                        doc.update_object(cmap_xref, f'<< /Length {len(cmap_bytes)} >>\nstream\n')
                        doc.update_stream(cmap_xref, cmap_bytes)
                        doc.xref_set_key(xref, 'ToUnicode', f'{cmap_xref} 0 R')
                        modified = True
                        differences_cmap = True

                # 3. /ToUnicode original apontando para a área de uso privado (Symbol, MT Extra) ou para U+FFFD (Cambria Math)
                tu = re.search(r'/ToUnicode\s+(\d+)\s+0\s+R', obj)
                base_font = re.search(r'/BaseFont\s*/(\S+)', obj)
                if tu and base_font and not differences_cmap and re.search(r'Symbol|MT-?Extra|CambriaMath', base_font.group(1)):
                    cmap_str = remap_tounicode_private_use(doc.xref_stream(int(tu.group(1))).decode('latin1'),
                                                           base_font.group(1))
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
        if not s:
            continue
        # Remove qualquer resíduo defensivo de ^{...} ou _{...} antes de QUESTÃO
        s = re.sub(r'^(?:[\^_]\{[^}]*\}\s*)+', '', s)
        # Rodapé com menção a caderno ou dia
        if re.search(r'CADERNO\s+\d+', s, re.IGNORECASE) and any(c in s.upper() for c in ['AZUL', 'AMARELO', 'VERDE', 'BRANCO', 'CINZA', 'ROSA', 'PÁGINA', 'PAGINA']):
            continue
        if re.search(r'\b(?:AMARELO|AZUL|CINZA|ROSA|BRANCO|VERDE|ARELO)?\s*[-–—|]?\s*P[ÁA]GINA\s*\d+', s, re.IGNORECASE):
            continue
        # Números de página isolados
        if re.match(r'^\d{1,2}$', s):
            continue
        # Ano isolado (ex: 2014, 2015, ENEM 2014) no topo da coluna
        if re.match(r'^(?:ENEM\s*)?20\d{2}\s*$', s, re.IGNORECASE):
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
        lines.append(s)

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

def wrap_inline_math(seg: str) -> str:
    """
    Envolve em $...$ variáveis indexadas e potências numéricas isoladas fora de fórmulas.
    """
    # Envolve variáveis indexadas isoladas: M_{1} -> $M_{1}$, E_{2} -> $E_{2}$, S_{1} -> $S_{1}$
    seg = re.sub(r'(?<![\$\w])([A-Za-z]_[0-9A-Za-z]+|[A-Za-z]_\{[^}]+\})(?![\$\w])', r'$\1$', seg)
    # Envolve potências numéricas isoladas: 10^{3} -> $10^{3}$
    seg = re.sub(r'(?<![\$\w])(\d+(?:\^[0-9A-Za-z]+|\^\{[^}]+\}))(?![\$\w])', r'$\1$', seg)
    return seg

# Símbolos Unicode -> LaTeX para células de tabela. De SYMBOL_MAP entram só as chaves Unicode
# (grego e operadores): as chaves ASCII/Latin-1 são códigos brutos da fonte Symbol e
# corromperiam texto comum (ex.: 'Ç' -> \cap, 'Í' -> \supset).
TABLE_CELL_MATH_MAP: Dict[str, str] = {
    **{k: v for k, v in SYMBOL_MAP.items() if ord(k) >= 0x370},
    **UNICODE_MATH_MAP,
    '−': '-',
}
TABLE_CELL_MATH_REGEX = re.compile('|'.join(re.escape(k) for k in sorted(TABLE_CELL_MATH_MAP, key=len, reverse=True)))

def format_table_cell(t: str) -> str:
    """
    Converte símbolos da célula para LaTeX, como no restante do texto. Célula que é uma
    expressão (sem prosa) vai inteira para $...$; com prosa, só variáveis e potências isoladas.
    """
    # Comando seguido de letra ganha espaço (\pi r, e não \pir)
    t = TABLE_CELL_MATH_REGEX.sub(
        lambda m: TABLE_CELL_MATH_MAP[m.group(0)] + (' ' if TABLE_CELL_MATH_MAP[m.group(0)][-1].isalpha()
                                                     and t[m.end():m.end() + 1].isalpha() else ''),
        t
    )
    has_math = bool(re.search(r'\\[a-zA-Z]+|[\^_]\{?\w', t)) or (
        bool(re.search(r'[<>=]', t)) and bool(re.search(r'(?<![\wÀ-ÿ])[A-Za-z](?![\wÀ-ÿ])', t))
    )
    has_prose = bool(re.search(r'[A-Za-zÀ-ÿ]{4,}', re.sub(r'\\[a-zA-Z]+', '', t)))
    if has_math and '$' not in t and not has_prose and not re.search('[ªº]', t):
        return f'${t}$'
    return wrap_inline_math(t)

def format_table_markdown(table: PageTable) -> str:
    """
    Converte uma tabela estruturada em Markdown (legenda opcional na primeira linha).
    """
    def cell(t: str) -> str:
        return format_table_cell(t).replace('|', r'\|')

    header, *body = table.rows
    lines = [cell(table.caption)] if table.caption else []
    lines.append('| ' + ' | '.join(cell(c) for c in header) + ' |')
    lines.append('|' + '---|' * len(header))
    lines += ['| ' + ' | '.join(cell(c) for c in r) + ' |' for r in body]
    return '\n'.join(lines)

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

    # Remove resíduos de parênteses escaláveis vazios e sobrescritos/subscritos vazios
    t = re.sub(r'\(\s*\)', ' ', t)
    t = re.sub(r'[\^_]\{\s*\}', '', t)

    # Se há delimitadores $, processa variáveis e potências isoladas apenas fora das fórmulas já existentes
    parts = t.split('$')
    if len(parts) > 1 and len(parts) % 2 == 1:
        for i in range(0, len(parts), 2):
            parts[i] = wrap_inline_math(parts[i])
        t = '$'.join(parts)
    else:
        t = wrap_inline_math(t)

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
        if group[0].group(1) == 'A' and set(letters) == {'A', 'B', 'C', 'D', 'E'}:
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
                # Alternativas gráficas em subcolunas: se alguma é só figura, o texto das demais são
                # rótulos de eixo dos gráficos (ex.: 'V (m^3) 0 15'), não o conteúdo da alternativa
                if IMAGE_ALT_PLACEHOLDER in alts.values():
                    alts = {let: IMAGE_ALT_PLACEHOLDER for let in 'ABCDE'}
                return sanitize_question_text(enun), alts

    clean_enunciado = sanitize_question_text(q_text)
    return clean_enunciado, {}


# Limite inferior padrão da mancha de texto (cadernos de ~780 pt de altura); páginas mais altas
# (A4, 826-842 pt, ex.: 2010 e 2014-2018) estendem o conteúdo até o rodapé localizado na página
DEFAULT_CONTENT_BOTTOM = 737.0
FOOTER_LINE_REGEX = re.compile(
    r'P[ÁA]GINA\s*\d+|CADERNO\s*\d+|\b(?:CH|CN|LC|MT|RED)\s*[-–—|•]\s*[12]\s*[ºo°]?\s*DIA|[12]\s*[ºo°]\s*DIA\s*•',
    re.IGNORECASE
)

def page_content_bottom(page: pymupdf.Page) -> float:
    """
    Coordenada vertical onde termina o conteúdo das questões: logo acima da linha de rodapé
    ('MT - 2º dia | Caderno 7 - AZUL - Página 25'), nunca acima de DEFAULT_CONTENT_BOTTOM.
    """
    footer_y = [
        l['bbox'][1]
        for b in page.get_text('dict', clip=pymupdf.Rect(0, page.rect.height * 0.85, page.rect.width, page.rect.height))['blocks']
        for l in b.get('lines', [])
        if FOOTER_LINE_REGEX.search(''.join(s['text'] for s in l['spans']))
    ]
    return max(DEFAULT_CONTENT_BOTTOM, min(footer_y) - 1.0) if footer_y else DEFAULT_CONTENT_BOTTOM

def is_vector_figure_drawing(d: dict, bottom: float = DEFAULT_CONTENT_BOTTOM) -> bool:
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
    if rect.y0 < 40 or rect.y1 > max(745.0, bottom) or rect.x0 < 25 or rect.x1 > 570:
        return False

    # Bounding boxes excessivamente grandes (moldura da página ou colunas inteiras)
    if w > 260 or h > 450:
        return False

    # Linha divisória de coluna vertical da página (ex: x~283.5, h > 400)
    if w < 1.0 and h > 400:
        return False

    # Linhas de cabeçalho da página ou divisórias horizontais completas
    if h < 1.0 and w > 230 and (rect.y0 < 85 or rect.y1 > 730):
        return False

    items = d.get('items', [])
    if not items:
        return False

    # 1. Curvas de Bézier cúbicas (gráficos de funções, círculos, elipses, arcos)
    for item in items:
        cmd = item[0]
        if cmd == 'c' and max(w, h) >= 12:
            return True

    # 2. Retângulos geométricos (caixas de gráficos, polígonos, cômodos de plantas, molduras de diagramas)
    for item in items:
        cmd = item[0]
        if cmd == 're':
            # Formas 2D com dimensões expressivas.
            # Tabelas sempre ocupam a largura inteira da coluna (w >= 230), portanto limitamos w < 230.
            if min(w, h) >= 15 and w < 230 and h < 350:
                return True
            # Barras de gráficos de colunas / barras (ex: w=4..40, h>=15)
            if min(w, h) >= 4.0 and max(w, h) >= 15.0 and min(w, h) <= 40.0 and w < 230:
                return True

    # 3. Linhas oblíquas / diagonais (geometria, eixos inclinados, polígonos)
    for item in items:
        cmd = item[0]
        if cmd == 'l':
            p1, p2 = item[1], item[2]
            dx = abs(p2.x - p1.x)
            dy = abs(p2.y - p1.y)
            if dx >= 5 and dy >= 5:
                return True

    # 4. Polilinhas / caminhos conectados multi-segmentos (rotas, setas, polígonos ortogonais)
    line_items = [it for it in items if it[0] == 'l']
    if len(line_items) >= 3 and w >= 15 and h >= 15 and w < 230:
        return True

    # 5. Quadriláteros oblíquos
    for item in items:
        if item[0] == 'qu':
            q = item[1]
            pts = [q.ul, q.ur, q.lr, q.ll, q.ul]
            for p1, p2 in zip(pts[:-1], pts[1:]):
                if abs(p2.x - p1.x) >= 5 and abs(p2.y - p1.y) >= 5:
                    return True

    return False

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

def is_answer_mark_ring(d: dict) -> bool:
    """
    Anel de marcação do gabarito em volta da letra correta (cadernos com gabarito de 2010 a 2014):
    elipse pequena só de contorno grosso colorido (verde ou verde-azulado), sem preenchimento.
    Não é figura da questão.
    """
    rect = d.get('rect')
    items = d.get('items', [])
    color = d.get('color') or ()
    return (bool(rect) and bool(items) and d.get('fill') is None and (d.get('width') or 0) >= 1.5
            and 10.0 <= max(rect.width, rect.height) <= 20.0 and len(color) == 3 and max(color) - min(color) >= 0.3
            and all(it[0] == 'c' for it in items))

def is_vector_cluster_noise(d: dict, bottom: float = DEFAULT_CONTENT_BOTTOM) -> bool:
    """
    Identifica elementos gráficos que não compõem figuras geométricas/diagramas reais,
    como réguas divisórias, margens, barras de fração horizontais e linhas de tabelas.
    """
    rect = d.get('rect')
    if not rect:
        return True
    w = rect.x1 - rect.x0
    h = rect.y1 - rect.y0
    # Margens e réguas de cabeçalho / rodapé / coluna
    if rect.y0 < 40 or rect.y1 > max(745.0, bottom) or rect.x0 < 25 or rect.x1 > 570:
        return True
    if w < 1.0 and h > 300:
        return True
    if h < 1.5 and w > 200:
        return True
    # Traços decorativos de título (hatching fino no cabeçalho)
    if h <= 4.0 and w > 50:
        return True
    # Filtra barras de fração puras ou linhas retas isoladas
    items = d.get('items', [])
    if len(items) == 1 and items[0][0] == 'l':
        p1, p2 = items[0][1], items[0][2]
        if abs(p1.y - p2.y) < 1.0 and abs(p1.x - p2.x) <= 80.0:
            return True
        # Filtra linhas retas ortogonais puras (bordas de grade de tabela)
        if abs(p1.x - p2.x) < 0.5 or abs(p1.y - p2.y) < 0.5:
            return True
    # Filtra pontos/bullets minúsculos
    if max(w, h) <= 5.0:
        return True
    return False

def detect_images_per_question(
    doc: pymupdf.Document,
    has_duplicate_languages: bool,
    page_tables: Dict[int, List[PageTable]]
) -> Set[Tuple[int, Optional[float]]]:
    """
    Identifica quais questões no documento PDF contêm imagens/figuras através de coordenadas espaciais,
    considerando tanto imagens raster (bitmap) quanto desenhos vetoriais (gráficos, geometrias, curvas).
    Tabelas estruturadas com sucesso (e seus desenhos de grade) não contam como imagem.
    """
    q_regions = []
    seen_1 = 0
    current_q = None
    current_lang = None
    bottoms = {p: max(745.0, page_content_bottom(doc[p])) for p in range(1, len(doc))}

    for page_num in range(1, len(doc)):
        page = doc[page_num]
        mid_x = page.rect.width / 2.0
        col_rects = detect_page_column_rects(page)
        is_single_col = (len(col_rects) == 1)
        blocks = [b for b in page.get_text("blocks") if 40 < b[1] < bottoms[page_num]]

        if is_single_col:
            columns = [sorted(blocks, key=lambda b: b[1])]
        else:
            left = sorted([b for b in blocks if b[0] < mid_x], key=lambda b: b[1])
            right = sorted([b for b in blocks if b[0] >= mid_x], key=lambda b: b[1])
            columns = [left, right]

        for col_idx, col_blocks in enumerate(columns):
            if not col_blocks:
                continue

            # Localiza cabeçalhos de questão nesta coluna
            header_indices = []
            for i, b in enumerate(col_blocks):
                m = re.search(r'QUEST[ÃA]O\s*[\n\r]*\s*(\d+)', b[4], re.IGNORECASE)
                if m:
                    header_indices.append((i, int(m.group(1)), b))

            # Se não há cabeçalhos na coluna, toda a coluna é continuação da questão anterior
            if not header_indices:
                if current_q is not None:
                    q_regions.append({
                        'num': current_q,
                        'lang': current_lang,
                        'page': page_num,
                        'col': col_idx,
                        'is_single_col': is_single_col,
                        'y0': col_blocks[0][1],
                        'header_y1': col_blocks[0][1],
                        'y1': col_blocks[-1][3]
                    })
                continue

            # Se há blocos de conteúdo antes do primeiro cabeçalho, pertencem à questão anterior
            first_header_idx, first_header_num, first_header_block = header_indices[0]
            if first_header_idx > 0 and current_q is not None:
                q_regions.append({
                    'num': current_q,
                    'lang': current_lang,
                    'page': page_num,
                    'col': col_idx,
                    'is_single_col': is_single_col,
                    'y0': col_blocks[0][1],
                    'header_y1': col_blocks[0][1],
                    'y1': first_header_block[1]
                })

            for k, (h_idx, q_num, h_block) in enumerate(header_indices):
                lang = None
                if has_duplicate_languages:
                    if q_num == 1:
                        seen_1 += 1
                    if q_num <= 5:
                        lang = 0.0 if seen_1 == 1 else 1.0

                current_q = q_num
                current_lang = lang
                q_start_y = h_block[1]
                header_bottom_y = h_block[3]

                if k + 1 < len(header_indices):
                    next_y = header_indices[k + 1][2][1]
                else:
                    next_y = col_blocks[-1][3]

                q_regions.append({
                    'num': current_q,
                    'lang': current_lang,
                    'page': page_num,
                    'col': col_idx,
                    'is_single_col': is_single_col,
                    'y0': q_start_y,
                    'header_y1': header_bottom_y,
                    'y1': next_y
                })

    questions_with_images = set()

    # Elementos repetidos na mesma posição em várias páginas (logotipo do cabeçalho, barras,
    # abas laterais) são decoração do caderno, não figuras de questão
    def position_key(r) -> Tuple[int, int, int, int]:
        return tuple(int(round(v / 2.0)) for v in (r[0], r[1], r[2], r[3]))

    drawings_by_page = {p: doc[p].get_drawings() for p in range(1, len(doc))}
    images_by_page = {p: doc[p].get_image_info() for p in range(1, len(doc))}
    min_repeats = max(3, 0.3 * (len(doc) - 1))
    drawing_counts = Counter(k for ds in drawings_by_page.values() for k in {position_key(d['rect']) for d in ds})
    image_counts = Counter(k for imgs in images_by_page.values() for k in {position_key(i['bbox']) for i in imgs if i.get('bbox')})
    decoration_drawings = {k for k, c in drawing_counts.items() if c >= min_repeats}
    decoration_images = {k for k, c in image_counts.items() if c >= min_repeats}

    for page_num in range(1, len(doc)):
        page = doc[page_num]
        mid_x = page.rect.width / 2.0
        col_rects = detect_page_column_rects(page)
        is_single_col = (len(col_rects) == 1)
        page_q_regions = [r for r in q_regions if r['page'] == page_num]

        # 1. Detecção de imagens raster (bitmap / fotos / escaneadas)
        images = images_by_page[page_num]
        for img in images:
            b = img.get('bbox')
            if not b or position_key(b) in decoration_images:
                continue
            w = b[2] - b[0]
            h = b[3] - b[1]

            # Ignora faixas laterais de margem, linhas finas e elementos fora da mancha de texto
            if w < 25 or h < 25 or b[0] > 550 or b[1] < 35 or b[3] > bottoms[page_num]:
                continue

            img_x_mid = (b[0] + b[2]) / 2.0
            img_col = 0 if (is_single_col or img_x_mid < mid_x) else 1
            img_y_mid = (b[1] + b[3]) / 2.0

            for r in page_q_regions:
                if r['is_single_col'] or r['col'] == img_col:
                    if (r['y0'] - 20) <= img_y_mid <= (r['y1'] + 20):
                        questions_with_images.add((r['num'], r['lang']))
                        break

        # 2. Tabelas detectadas que não puderam ser estruturadas em texto são tratadas como imagem
        tables = page_tables.get(page_num, [])
        for tab in tables:
            if tab.accepted:
                continue
            t_bbox = tab.bbox
            t_mid_x = (t_bbox[0] + t_bbox[2]) / 2.0
            t_col = 0 if (is_single_col or t_mid_x < mid_x) else 1
            t_mid_y = (t_bbox[1] + t_bbox[3]) / 2.0
            for r in page_q_regions:
                if r['is_single_col'] or r['col'] == t_col:
                    if (r['y0'] - 15) <= t_mid_y <= (r['y1'] + 15):
                        questions_with_images.add((r['num'], r['lang']))
                        break

        # 3. Detecção de figuras vetoriais (gráficos de funções, esquemas geométricos, polígonos, curvas)
        # Desenhos de grade e fundo das tabelas estruturadas não são figuras
        accepted_rects = [t.bbox + (-2, -2, 2, 2) for t in tables if t.accepted]
        page_drawings = [
            d for d in drawings_by_page[page_num]
            if position_key(d['rect']) not in decoration_drawings and not any(d['rect'] in r for r in accepted_rects)
            and not is_answer_mark_ring(d)
        ]

        # 3a. Checagem individual via is_vector_figure_drawing
        for drawing in page_drawings:
            if not is_vector_figure_drawing(drawing, bottoms[page_num]):
                continue
            rect = drawing['rect']
            draw_x_mid = (rect.x0 + rect.x1) / 2.0
            draw_col = 0 if (is_single_col or draw_x_mid < mid_x) else 1
            draw_y_mid = (rect.y0 + rect.y1) / 2.0

            for r in page_q_regions:
                if r['is_single_col'] or r['col'] == draw_col:
                    if (r['y0'] - 20) <= draw_y_mid <= (r['y1'] + 20):
                        questions_with_images.add((r['num'], r['lang']))
                        break

        # 2b. Checagem de cluster vetorial (para esquemas compostos por curvas de Bézier agrupadas)
        for r in page_q_regions:
            if (r['num'], r['lang']) in questions_with_images:
                continue

            body_y0 = r['header_y1'] + 2.0
            q_col = r['col']

            q_drawings = []
            for d in page_drawings:
                if is_vector_cluster_noise(d, bottoms[page_num]):
                    continue
                rect = d['rect']
                d_mid_x = (rect.x0 + rect.x1) / 2.0
                d_col = 0 if (r['is_single_col'] or d_mid_x < mid_x) else 1
                d_mid_y = (rect.y0 + rect.y1) / 2.0

                if (r['is_single_col'] or d_col == q_col) and (body_y0 <= d_mid_y <= r['y1'] + 10):
                    q_drawings.append(d)

            beziers = sum(1 for d in q_drawings if any(it[0] == 'c' for it in d.get('items', [])))
            if q_drawings:
                min_x = min(d['rect'].x0 for d in q_drawings)
                max_x = max(d['rect'].x1 for d in q_drawings)
                min_y = min(d['rect'].y0 for d in q_drawings)
                max_y = max(d['rect'].y1 for d in q_drawings)
                span_w = max_x - min_x
                span_h = max_y - min_y
                # Curvas agrupadas, ou muitas formas pequenas (ex.: plateia de poltronas em retângulos, 2013)
                if (beziers >= 6 and span_w >= 25 and span_h >= 10) or (len(q_drawings) >= 20 and span_w >= 50 and span_h >= 50):
                    questions_with_images.add((r['num'], r['lang']))

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

def extract_column_math_text(
    page: pymupdf.Page,
    clip_rect: pymupdf.Rect,
    tables: Optional[List[PageTable]] = None,
    bottom: float = DEFAULT_CONTENT_BOTTOM
) -> str:
    """
    Extrai o conteúdo textual de uma coluna ou região da página reconstruindo
    fórmulas matemáticas em LaTeX bidimensionalmente (frações, raízes, potências, matrizes).
    O texto de tabelas estruturadas é substituído por um marcador TABLE_PLACEHOLDER na posição da tabela.
    """
    tables = tables or []
    dict_data = page.get_text("dict", clip=clip_rect)
    spans = []
    for b in dict_data.get("blocks", []):
        if "lines" in b:
            for l in b["lines"]:
                for s in l["spans"]:
                    t = s["text"].replace(HAIR_SPACE, '')
                    # Ignora spans contendo apenas espaços em branco
                    if not t or not t.strip():
                        continue
                    t = MATH_ALNUM_REGEX.sub(lambda m: unicodedata.normalize('NFKC', m.group(1)), t)
                    # A Cambria Math declara ascendente/descendente enormes (caixa de ~5,6 vezes o corpo):
                    # a caixa vertical é refeita pela linha de base, senão o sinal (−, ×, π) cai no
                    # filtro de divisores verticais abaixo
                    if 'Cambria' in s["font"] and (s["bbox"][3] - s["bbox"][1]) > 2.5 * s["size"]:
                        base_y = s["origin"][1]
                        s["bbox"] = (s["bbox"][0], base_y - 0.8 * s["size"], s["bbox"][2], base_y + 0.25 * s["size"])
                    # Filtra cabeçalhos e rodapés de página por coordenadas verticais
                    if s["bbox"][3] <= 45.0 or s["bbox"][1] >= bottom:
                        continue
                    # Filtra marcas d'água e divisores verticais de coluna
                    if re.search(r'(ENEM\s*20[0-9A-Z]{2}\s*){2,}', t, re.IGNORECASE) or (s["bbox"][3] - s["bbox"][1]) > 50.0:
                        continue
                    if re.search(r'\*[0-9A-Za-z_–-]+\*', t):
                        continue
                    font = s["font"]
                    is_lb = "Symbol" in font and (any(c in t for c in '\x1b\x1c\x1d') or any(ord(c) in (27, 28, 29) for c in t))
                    is_rb = "Symbol" in font and (any(c in t for c in '\x18\x19\x1a') or any(ord(c) in (24, 25, 26) for c in t))
                    if "Symbol" in font:
                        # Fonte Symbol sem /ToUnicode cujo nome de glifo cai na área privada
                        # (U+F000 + código, ou peças de delimitadores da Adobe como 'bracketlefttp')
                        t = ''.join(remap_private_use(ord(ch), font) or ch if 0xE000 <= ord(ch) <= 0xF8FF else ch
                                    for ch in t)
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

    # Tabelas estruturadas: seu texto sai do fluxo e um marcador ocupa a posição da tabela
    composite_elements = []
    for t_idx, tab in enumerate(tables):
        if not tab.accepted:
            continue
        for s in spans:
            cx = (s['bbox'][0] + s['bbox'][2]) / 2.0
            cy = (s['bbox'][1] + s['bbox'][3]) / 2.0
            if tab.bbox.contains(pymupdf.Point(cx, cy)):
                s["used"] = True
        t_center = pymupdf.Point((tab.bbox.x0 + tab.bbox.x1) / 2.0, (tab.bbox.y0 + tab.bbox.y1) / 2.0)
        if clip_rect.contains(t_center):
            composite_elements.append({
                "text": TABLE_PLACEHOLDER.format(page.number, t_idx),
                "bbox": list(tab.bbox),
                "origin": [tab.bbox.x0, tab.bbox.y1],
                "size": 10.0,
                "is_math": False
            })

    # Coleta desenhos vetoriais na coluna (linhas horizontais de frações e radicais)
    hlines = []
    radicals = []
    for d in page.get_drawings():
        r = d['rect']
        if r.y0 < 40 or r.y1 > bottom or r.x1 < clip_rect.x0 or r.x0 > clip_rect.x1:
            continue
        items = d.get('items', [])
        lines = [it for it in items if it[0] == 'l']
        if len(lines) >= 4 and 8.0 <= (r.x1 - r.x0) <= 120.0 and 6.0 <= (r.y1 - r.y0) <= 35.0:
            horiz_top = [l for l in lines if abs(l[1].y - l[2].y) < 1.0 and abs(l[1].y - r.y0) < 3.0]
            # A barra do radical é a união dos segmentos horizontais do topo: no glifo √ preenchido
            # (contorno, ex.: 2021) o primeiro segmento é só um trecho de borda de ~1 pt
            xs = [p.x for l in horiz_top for p in (l[1], l[2])]
            # Haste do √: sobe para a direita, da base do desenho até a ponta esquerda da barra, com o
            # gancho à esquerda da base (descarta molduras, faces de polígonos e polilinhas de gráficos)
            def is_radical_stem(l) -> bool:
                top, foot = sorted((l[1], l[2]), key=lambda p: p.y)
                return (top.x - foot.x >= 1.0 and top.y <= r.y0 + 3.0 and foot.y >= r.y1 - 2.0
                        and abs(top.x - min(xs)) <= 2.0 and foot.x - r.x0 >= 1.0)

            if horiz_top and any(is_radical_stem(l) for l in lines):
                radicals.append((r, min(xs), max(xs)))
                continue

        # Barra de fração desenhada como retângulo fino preenchido em contorno de segmentos
        # parciais (ex.: 2021): vira uma única barra com a largura total do desenho
        if lines and len(lines) == len(items) and d.get('fill') is not None and (r.y1 - r.y0) < 1.5:
            if 2.0 <= (r.x1 - r.x0) <= 80.0 and clip_rect.x0 - 5 <= r.x0 and r.x1 <= clip_rect.x1 + 5:
                hlines.append((r.x0, (r.y0 + r.y1) / 2.0, r.x1, (r.y0 + r.y1) / 2.0))
            continue

        for it in items:
            if it[0] == 'l':
                p1, p2 = it[1], it[2]
                if abs(p1.y - p2.y) < 1.0:
                    x0, x1 = min(p1.x, p2.x), max(p1.x, p2.x)
                    if 2.0 <= (x1 - x0) <= 80.0 and clip_rect.x0 - 5 <= x0 and x1 <= clip_rect.x1 + 5:
                        hlines.append((x0, (p1.y + p2.y) / 2.0, x1, (p1.y + p2.y) / 2.0))

    # 1. Reconstrução de Radicais (\sqrt{...} ou \sqrt[n]{...})
    for r, rx0, rx1 in radicals:
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
                # Linha de base do radicando (a ponta do glifo √ desce abaixo dela)
                "origin": [r.x0, max(rad_spans, key=lambda s: s['size'])['origin'][1]],
                "size": max(s["size"] for s in rad_spans),
                "is_math": True
            })

    # Caixas delimitadoras de tabelas protegem suas linhas internas de virarem frações
    tab_rects = [t.bbox for t in tables]

    # 2. Reconstrução de Frações (\frac{num}{den})
    for x0, y, x1, _ in sorted(hlines, key=lambda h: (h[1], h[0])):
        # Ignora linhas horizontais que interceptam tabelas estruturadas
        if any(r.intersects(pymupdf.Rect(x0, y - 2.0, x1, y + 2.0)) for r in tab_rects):
            continue
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

        # Ordinais ª/º desenhados como letra sobrescrita + traço curto: o traço não é barra de fração
        if (x1 - x0) <= 6.0 and not num_comp and len(num_spans) == 1 \
                and num_spans[0]['text'].strip() in ('a', 'o') and num_spans[0]['size'] < 7.5:
            continue

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

    sorted_items = sorted(remaining, key=lambda it: (it["bbox"][1] + it["bbox"][3]) / 2.0)

    lines = []
    for it in sorted_items:
        y_mid = (it["bbox"][1] + it["bbox"][3]) / 2.0
        # Spans pertencem à mesma linha apenas se a distância vertical for de até 4.5 pontos
        if lines and abs(y_mid - lines[-1]["y_mid"]) <= 4.5:
            lines[-1]["items"].append(it)
            lines[-1]["y0"] = min(lines[-1]["y0"], it["bbox"][1])
            lines[-1]["y1"] = max(lines[-1]["y1"], it["bbox"][3])
            lines[-1]["y_mid"] = (lines[-1]["y0"] + lines[-1]["y1"]) / 2.0
        else:
            lines.append({
                "y_mid": y_mid,
                "y0": it["bbox"][1],
                "y1": it["bbox"][3],
                "items": [it]
            })

    formatted_lines = []
    for line_dict in lines:
        line = line_dict["items"]
        line.sort(key=lambda item: item["bbox"][0])
        # Tamanho e linha de base de referência vêm do texto comum da linha: elementos compostos
        # (frações, radicais) e sinais avulsos (vírgula ampliada, glifos de controle) os distorcem
        text_items = [item for item in line if "font" in item and re.search(r'\w', item["text"])] or line
        base_size = max(item["size"] for item in text_items)
        base_items_in_line = [item for item in text_items if item["size"] >= base_size * 0.85]
        base_orig_y = base_items_in_line[0]["origin"][1] if base_items_in_line else line[0]["origin"][1]

        line_tokens = []
        for item in line:
            t = item["text"]
            if item["size"] < base_size * 0.85 and t.strip():
                if item["origin"][1] > base_orig_y + 1.2:
                    t = f"_{{{t}}}"
                elif item["origin"][1] < base_orig_y - 1.2 or (item.get("is_math") and item["bbox"][3] <= base_orig_y):
                    # Ordinal sobrescrito após número (1ª, 2º)
                    if t.strip() in ('a', 'o') and line_tokens and line_tokens[-1][0].rstrip()[-1:].isdigit():
                        t = 'ª' if t.strip() == 'a' else 'º'
                    else:
                        t = f"^{{{t}}}"
            line_tokens.append((t, item))

        res_str = ""
        prev_item = None
        for t, item in line_tokens:
            if prev_item:
                gap = item["bbox"][0] - prev_item["bbox"][2]
                if gap > 1.8 and not res_str.endswith(" ") and not t.startswith((" ", "^", "_", "ª", "º")):
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

        # Limpeza defensiva de sobrescrito ou subscrito vazio
        res_str = re.sub(r'[\^_]\{\s*\}', '', res_str)

        if any(sym in res_str for sym in [r'\frac', r'\sqrt', r'\begin{pmatrix}']):
            clean_text = re.sub(r'\\[a-zA-Z]+', '', res_str)
            prose_words = [w for w in re.findall(r'\b[a-zA-ZÀ-ÿ]{3,}\b', clean_text)]
            if len(prose_words) >= 2:
                # Linha de prosa contendo fórmula inline: envolve apenas as fórmulas matemáticas em $ ... $
                res_str = re.sub(r'(\d+\s+)?(\\frac\{[^{}]+\}\{[^{}]+\})', r'$\g<0>$', res_str)
                res_str = re.sub(r'(\\sqrt(?:\[[^\]]+\])?\{[^{}]+\})', r'$\g<0>$', res_str)
            else:
                # Linha de equação matemática pura (não inicia por letra de alternativa isolada)
                if not res_str.strip().startswith('$') and not re.match(r'^[A-E]\b', res_str.strip()):
                    res_str = f"${res_str.strip()}$"

        formatted_lines.append(res_str.strip())

    return "\n".join(l for l in formatted_lines if l)


def extract_page_column_text(page: pymupdf.Page, tables: Optional[List[PageTable]] = None) -> str:
    """
    Extrai o texto da página respeitando a geometria das colunas e reconstruindo
    fórmulas matemáticas em formato LaTeX padronizado.
    """
    column_rects = detect_page_column_rects(page)
    bottom = page_content_bottom(page)
    col_texts = []
    for rect in column_rects:
        raw_col = extract_column_math_text(page, rect, tables, bottom)
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

    # Detecta e estrutura as tabelas uma única vez por página
    page_tables: Dict[int, List[PageTable]] = {p: extract_page_tables(doc[p]) for p in range(1, len(doc))}
    tables_markdown: Dict[Tuple[int, int], str] = {
        (p, i): format_table_markdown(t)
        for p, tabs in page_tables.items() for i, t in enumerate(tabs) if t.accepted
    }

    def insert_tables(text: str) -> str:
        return TABLE_PLACEHOLDER_REGEX.sub(
            lambda m: '\n' + tables_markdown[(int(m.group(1)), int(m.group(2)))] + '\n', text
        ).strip()

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
        pages_text.append(extract_page_column_text(page, page_tables.get(p)))
    full_text = "\n".join(pages_text)

    # Detecta previamente alternativas representadas por desenhos vetoriais (ex: 2010 Regular)
    vector_circle_alts = extract_vector_circle_alternatives(doc)

    # Verifica se há ocorrência múltipla das Questões 1 e 2 (indicador real de Inglês/Espanhol)
    q1_count = len(re.findall(r'(?:^|\n)\s*QUEST[ÃA]O\s+1(?:\D|$)', full_text, flags=re.IGNORECASE))
    q2_count = len(re.findall(r'(?:^|\n)\s*QUEST[ÃA]O\s+2(?:\D|$)', full_text, flags=re.IGNORECASE))
    has_duplicate_languages = (q1_count >= 2 and q2_count >= 2)

    # Detecta imagens nas questões
    questions_with_spatial_images = detect_images_per_question(doc, has_duplicate_languages, page_tables)

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
        has_table = any(TABLE_PLACEHOLDER_REGEX.search(t) for t in [enunciado] + list(alts.values()))
        # Referência a tabela/quadro só indica imagem quando nenhuma tabela da questão foi estruturada
        has_explicit_ref = bool(EXPLICIT_IMAGE_REGEX.search(enunciado)) or (
            bool(EXPLICIT_TABLE_REGEX.search(enunciado)) and not has_table
        )
        has_image = 1 if (has_img_in_alts or has_spatial_img or has_explicit_ref) else 0

        key = (q_num, lang)
        parsed_questions[key] = {
            'CO_POSICAO': q_num,
            'TP_LINGUA': lang,
            'DESC_ENUNCIADO': insert_tables(enunciado),
            'DESC_ALTER_A': insert_tables(alts.get('A', '')),
            'DESC_ALTER_B': insert_tables(alts.get('B', '')),
            'DESC_ALTER_C': insert_tables(alts.get('C', '')),
            'DESC_ALTER_D': insert_tables(alts.get('D', '')),
            'DESC_ALTER_E': insert_tables(alts.get('E', '')),
            'IN_ITEM_IMAGEM': has_image,
            'IN_ITEM_TABELA': 1 if has_table else 0,
            'REF_ARQUIVO_PDF': pdf_path.name
        }

    return parsed_questions
