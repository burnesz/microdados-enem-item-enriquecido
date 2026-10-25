"""
Módulo para extração estruturada de tabelas dos cadernos do ENEM.

O `page.find_tables()` do PyMuPDF localiza bem o contorno das tabelas, mas erra o preenchimento
das células no estilo típico do ENEM (réguas horizontais sem réguas verticais nas linhas de dados).
Aqui o contorno vem do PyMuPDF; as linhas vêm das réguas horizontais e as colunas das réguas
verticais e dos vãos verticais entre palavras. Toda tabela passa por um controle de qualidade:
apenas as aprovadas (status 'OK') são estruturadas; as demais seguem tratadas como imagem.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import re
import pymupdf

TABLE_STATUS_OK = 'OK'

# Vão horizontal mínimo (pt) sem palavras para separar colunas por projeção
COL_GAP = 5.0
# Fração mínima da largura da tabela coberta por uma régua para delimitar linhas
ROW_RULE_COVERAGE = 0.3
# Fração mínima da largura coberta por uma régua "cheia" (bordas superior/inferior, cabeçalho)
FULL_RULE_COVERAGE = 0.8
# Fração máxima de células vazias aceita (desconsiderando o canto superior esquerdo)
MAX_EMPTY_CELL_RATIO = 0.15

# Célula de dados com vários números separados por espaço (linhas fundidas), exceto milhar ("5 000")
MERGED_NUMBERS_REGEX = re.compile(r'^-?\d[\d,.]*(?:\s+(?!\d{3}(?:\D|$))-?\d[\d,.]*)+$')


@dataclass
class PageTable:
    bbox: pymupdf.Rect
    status: str
    caption: str = ''
    rows: List[List[str]] = field(default_factory=list)

    @property
    def accepted(self) -> bool:
        return self.status == TABLE_STATUS_OK


@dataclass
class _Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    size: float
    base_y: float
    font: str

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2.0


def _normalize_char(c: str) -> str:
    # Mesmos resíduos de fontes InDesign tratados em clean_page_text
    if c == '\x0f':
        return ','
    if c == '\x11':
        return '.'
    if c == '¿':
        return 'fi'
    if c == '\x03' or ord(c) < 32:
        return ' '
    return c


def _page_words(page: pymupdf.Page) -> List[_Word]:
    """
    Monta as palavras da página a partir dos caracteres (rawdict), preservando tamanho de fonte e
    linha de base para reconstruir sobrescritos, subscritos e ordinais dentro das células.
    Sem recorte (clip): o contorno do find_tables pode cortar a 1ª coluna sem borda esquerda,
    e o clip descartaria as letras que ficam para fora.
    """
    words = []
    for b in page.get_text('rawdict').get('blocks', []):
        for l in b.get('lines', []):
            for s in l['spans']:
                cur: List[Tuple[pymupdf.Rect, str]] = []
                for ch in s['chars'] + [None]:
                    if ch and ch['c'] == '\u200a':  # espaço fino entre letra e índice: não separa palavras
                        continue
                    t = _normalize_char(ch['c']) if ch else ' '
                    if t.strip():
                        cur.append((pymupdf.Rect(ch['bbox']), t))
                        continue
                    if cur:
                        r = pymupdf.Rect(cur[0][0])
                        for cr, _ in cur[1:]:
                            r |= cr
                        words.append(_Word(r.x0, r.y0, r.x1, r.y1, ''.join(c for _, c in cur),
                                           s['size'], s['origin'][1], s['font']))
                        cur = []
    return words


def _words_in(words: List[_Word], bbox: pymupdf.Rect) -> List[_Word]:
    """Palavras com mais da metade da área dentro do contorno (incluídas por inteiro)."""
    out = []
    for w in words:
        r = pymupdf.Rect(w.x0, w.y0, w.x1, w.y1)
        if r.intersect(bbox).get_area() > 0.5 * max(r.get_area(), 1e-6):
            out.append(w)
    return out


def _cell_graphics(drawings: List[Dict[str, Any]], bbox: pymupdf.Rect, words: List[_Word]) -> Optional[str]:
    """
    Detecta elementos gráficos que o texto não representa: traços diagonais (radicais, setas,
    figuras) e barras de fração (traço curto com texto colado acima e abaixo).
    """
    for d in drawings:
        if not d['rect'].intersects(bbox):
            continue
        for it in d['items']:
            if it[0] != 'l' or not (it[1] in bbox and it[2] in bbox):
                continue
            p1, p2 = it[1], it[2]
            dx, dy = abs(p1.x - p2.x), abs(p1.y - p2.y)
            if dx > 1.5 and dy > 1.5:
                return 'traços diagonais (radical/figura)'
            if dy < 1.0 and 4.0 <= dx < 30.0:
                x0, x1, y = min(p1.x, p2.x), max(p1.x, p2.x), (p1.y + p2.y) / 2.0
                over = [w for w in words if x0 - 2 <= w.cx <= x1 + 2]
                num = [w for w in over if 0 <= y - w.y1 <= 4.0]
                den = [w for w in over if 0 <= w.y0 - y <= 4.0]
                # A barra tem o comprimento do numerador/denominador; régua de célula é bem mais larga
                if num and den and dx <= max(w.x1 - w.x0 for w in num + den) + 6.0:
                    return 'fração em célula'
    return None


def _rules(drawings: List[Dict[str, Any]], bbox: pymupdf.Rect) -> Tuple[list, list]:
    """Réguas horizontais (x0, x1, y) e verticais (y0, y1, x) que tocam a tabela."""
    hs, vs = [], []
    near = [d for d in drawings if d['rect'].intersects(bbox)]
    # Faixas de fundo empilhadas dentro de um fundo da mesma cor (ex.: uma por linha de texto
    # do cabeçalho) têm bordas invisíveis e não delimitam linhas nem colunas
    fills = [(it[1], d.get('fill')) for d in near if d.get('type') == 'f' for it in d['items']
             if it[0] == 're' and it[1].width >= 1.5 and it[1].height >= 1.5]

    def hidden_fill(r: pymupdf.Rect, color) -> bool:
        return any(c == color and o != r and r in (o + (-0.5, -0.5, 0.5, 0.5)) for o, c in fills)

    for d in near:
        for it in d['items']:
            if it[0] == 'l':
                p1, p2 = it[1], it[2]
                if abs(p1.y - p2.y) < 1.0:
                    hs.append((min(p1.x, p2.x), max(p1.x, p2.x), (p1.y + p2.y) / 2.0))
                elif abs(p1.x - p2.x) < 1.0:
                    vs.append((min(p1.y, p2.y), max(p1.y, p2.y), (p1.x + p2.x) / 2.0))
            elif it[0] == 're':
                r = it[1]
                if r.height < 1.5:
                    hs.append((r.x0, r.x1, (r.y0 + r.y1) / 2.0))
                elif r.width < 1.5:
                    vs.append((r.y0, r.y1, (r.x0 + r.x1) / 2.0))
                elif not (d.get('type') == 'f' and hidden_fill(r, d.get('fill'))):
                    hs += [(r.x0, r.x1, r.y0), (r.x0, r.x1, r.y1)]
                    vs += [(r.y0, r.y1, r.x0), (r.y0, r.y1, r.x1)]
    return hs, vs


def _cluster(vals: List[float], tol: float = 3.0) -> List[float]:
    groups: List[List[float]] = []
    for v in sorted(vals):
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


def _merge_collinear(hs: list, tol: float = 1.5, gap: float = 3.0) -> List[Tuple[float, float]]:
    """
    Une segmentos horizontais na mesma altura (réguas desenhadas célula a célula)
    e retorna (y, cobertura efetiva em pt) por altura.
    """
    out = []
    for y in _cluster([h[2] for h in hs], tol):
        segs = sorted((x0, x1) for x0, x1, yy in hs if abs(yy - y) <= tol)
        cov, cur = 0.0, list(segs[0])
        for a, b in segs[1:]:
            if a - cur[1] <= gap:
                cur[1] = max(cur[1], b)
            else:
                cov += cur[1] - cur[0]
                cur = [a, b]
        cov += cur[1] - cur[0]
        out.append((y, cov))
    return out


def _expand_bbox(drawings: List[Dict[str, Any]], bbox: pymupdf.Rect, gap: float = 3.0) -> pymupdf.Rect:
    """
    O find_tables pode deixar de fora colunas sem borda vertical (ex.: 1ª ou última coluna).
    As réguas horizontais percorrem a largura inteira da tabela: o contorno é estendido até a
    extensão compartilhada por pelo menos duas réguas que cruzam o contorno original.
    """
    band = pymupdf.Rect(-1e4, bbox.y0 - 2, 1e4, bbox.y1 + 2)
    hs, _ = _rules(drawings, band)
    hs = [h for h in hs if bbox.y0 - 2 <= h[2] <= bbox.y1 + 2]
    extents = []
    for y in _cluster([h[2] for h in hs], 1.5):
        segs = sorted((x0, x1) for x0, x1, yy in hs if abs(yy - y) <= 1.5)
        cur = list(segs[0])
        for a, b in segs[1:] + [(1e9, 1e9)]:
            if a - cur[1] <= gap:
                cur[1] = max(cur[1], b)
                continue
            if min(cur[1], bbox.x1) - max(cur[0], bbox.x0) > 0.5 * bbox.width:
                extents.append((cur[0], cur[1]))
            cur = [a, b]
    shared = [e for e in extents
              if sum(1 for f in extents if abs(f[0] - e[0]) <= 3 and abs(f[1] - e[1]) <= 3) >= 2]
    if not shared:
        return bbox
    x0, x1 = max(shared, key=lambda e: e[1] - e[0])
    return pymupdf.Rect(min(bbox.x0, x0), bbox.y0, max(bbox.x1, x1), bbox.y1)


def _text_lines(words: List[_Word]) -> List[List[_Word]]:
    """Agrupa palavras por linha visual (centro vertical), tolerando sobrescritos e subscritos."""
    lines: List[Tuple[float, List[_Word]]] = []
    for w in sorted(words, key=lambda w: w.cy):
        if lines:
            height = max(x.y1 - x.y0 for x in lines[-1][1] + [w])
            if w.cy - lines[-1][0] <= 0.6 * height:
                lines[-1][1].append(w)
                continue
        lines.append((w.cy, [w]))
    return [sorted(ws, key=lambda w: w.x0) for _, ws in lines]


def _cell_text(words: List[_Word]) -> str:
    """Texto da célula com sobrescritos (^{...}), subscritos (_{...}) e ordinais (ª, º)."""
    parts = []
    for line in _text_lines(words):
        base = max(w.size for w in line)
        base_y = next(w.base_y for w in line if w.size >= base * 0.85)
        out, prev = '', None
        for w in line:
            t = w.text
            if w.size < base * 0.85:
                if w.base_y < base_y - 1.2:
                    if t in ('a', 'o') and out[-1:].isdigit():
                        t = 'ª' if t == 'a' else 'º'
                    else:
                        t = f'^{{{t}}}'
                elif w.base_y > base_y + 1.2:
                    t = f'_{{{t}}}'
            # Vão entre palavras, ou sobreposição horizontal (texto rotacionado), separa com espaço
            gap = w.x0 - prev.x1 if prev is not None else 0.0
            if prev is not None and (gap > 0.8 or gap < -1.0) and not t.startswith(('^', '_', 'ª', 'º')):
                out += ' '
            out += t
            prev = w
        # Hifenização do português repete o hífen na linha seguinte ("Matéria-" / "-prima")
        if parts and parts[-1].endswith('-') and out.startswith('-'):
            parts[-1] += out[1:]
        else:
            parts.append(out)
    return ' '.join(parts).strip()


def extract_table(
    bbox: pymupdf.Rect,
    drawings: List[Dict[str, Any]],
    page_words: List[_Word],
    row_ys: List[float]
) -> PageTable:
    """
    Estrutura a tabela contida em bbox e aplica o controle de qualidade.
    row_ys são as fronteiras de linha do próprio find_tables, que reconstrói bordas
    a partir de retângulos de fundo quando não há réguas desenhadas.
    """
    bbox = _expand_bbox(drawings, pymupdf.Rect(bbox))
    words = _words_in(page_words, bbox)
    if not words:
        return PageTable(bbox, 'sem texto')
    if any('BundesbahnPi' in w.font for w in words) or any(re.match(r'QUEST[ÃA]O$', w.text, re.I) for w in words):
        return PageTable(bbox, 'alternativas ou cabeçalho de questão na área')

    # Curvas de Bézier dentro da área indicam figura/gráfico (tabelas são só retas)
    for d in drawings:
        if d['rect'].intersects(bbox) and any(it[0] == 'c' and (it[1] in bbox or it[4] in bbox) for it in d['items']):
            return PageTable(bbox, 'curvas (figura)')
    graphics = _cell_graphics(drawings, bbox, words)
    if graphics:
        return PageTable(bbox, graphics)

    hs, vs = _rules(drawings, bbox)
    width = bbox.width
    merged = [(y, cov) for y, cov in _merge_collinear(hs) if bbox.y0 - 2 <= y <= bbox.y1 + 2] if hs else []
    if sum(1 for _, cov in merged if cov >= FULL_RULE_COVERAGE * width) < 2:
        return PageTable(bbox, 'poucas réguas horizontais (gráfico?)')

    # Faixas de linha: bordas do contorno + réguas que cobrem parte relevante da largura
    ys = _cluster([bbox.y0, bbox.y1] + [y for y, cov in merged if cov >= ROW_RULE_COVERAGE * width]
                  + [y for y in row_ys if bbox.y0 <= y <= bbox.y1])
    bands: List[List[_Word]] = [[] for _ in range(max(len(ys) - 1, 1))]
    for w in words:
        bands[min(sum(1 for y in ys[1:-1] if w.cy > y), len(bands) - 1)].append(w)
    bands = [b for b in bands if b]
    if len(bands) < 2:
        return PageTable(bbox, 'degenerada')

    # Colunas: vãos de projeção e réguas verticais, medidos nas faixas de dados
    # (as primeiras faixas podem conter título ou cabeçalho que atravessa colunas)
    skip = 1 if len(bands) <= 3 else 2
    body = [w for b in bands[skip:] for w in b] or words
    rule_xs = [x for x in _cluster([v[2] for v in vs if bbox.x0 + 3 < v[2] < bbox.x1 - 3])
               if not any(w.x0 + 1 < x < w.x1 - 1 for w in body)]
    xs = list(rule_xs)
    head = [(w.x0, w.x1) for w in words if w not in body]

    def gap_boundary(g0: float, g1: float) -> float:
        # Ponto do vão livre de palavras do cabeçalho mais próximo do centro; se o cabeçalho
        # cobre o vão inteiro (colspan real), fica o centro
        mid = (g0 + g1) / 2.0
        covered = sorted((max(a, g0), min(b, g1)) for a, b in head if a < g1 and b > g0)
        free, x = [], g0
        for a, b in covered:
            if a > x:
                free.append((x, a))
            x = max(x, b)
        if x < g1:
            free.append((x, g1))
        if not free:
            return mid
        return min((min(max(mid, a), b) for a, b in free), key=lambda p: abs(p - mid))

    spans = sorted((w.x0, w.x1) for w in body)
    cur = list(spans[0])
    for a, b in spans[1:]:
        if a - cur[1] >= COL_GAP:
            # Um vão já delimitado por régua vertical não gera fronteira extra
            if not any(cur[1] - 1 <= x <= a + 1 for x in rule_xs):
                xs.append(gap_boundary(cur[1], a))
            cur = [a, b]
        else:
            cur[1] = max(cur[1], b)
    bounds = _cluster(xs)
    ncols = len(bounds) + 1

    def rule_crosses(x: float, y0: float, y1: float) -> bool:
        return any(abs(v[2] - x) < 2.0 and min(v[1], y1) - max(v[0], y0) >= 0.5 * (y1 - y0) for v in vs)

    def col_of(x: float) -> int:
        return sum(1 for b in bounds if x > b)

    # Título que atravessa colunas na primeira faixa vira legenda
    caption = ''
    first = _text_lines(bands[0])
    if len(first) == 1 and bounds:
        run = first[0]
        contiguous = all(b.x0 - a.x1 < 6.0 for a, b in zip(run, run[1:]))
        y0, y1 = min(w.y0 for w in run), max(w.y1 for w in run)
        crossed = [b for b in bounds if run[0].x0 < b < run[-1].x1]
        if contiguous and crossed and not any(rule_crosses(b, y0, y1) for b in crossed):
            caption = _cell_text(run)
            bands = bands[1:]

    rows: List[List[str]] = []
    for b_idx, band in enumerate(bands):
        # Faixa sem réguas internas: cada linha de texto com rótulo na 1ª coluna e número em outra
        # coluna (âncora) inicia uma linha da tabela. Continuações (ex.: "(m)" num cabeçalho) só são
        # aceitas antes da 2ª âncora; depois dela, células de várias linhas tornam o pareamento ambíguo.
        lines = _text_lines(band)

        def spans_columns(ln: List[_Word]) -> bool:
            return any(col_of(w.cx) == 0 for w in ln) and len({col_of(w.cx) for w in ln}) >= 2

        anchors = [i for i, ln in enumerate(lines)
                   if spans_columns(ln) and any(col_of(w.cx) > 0 and re.search(r'\d', w.text) for w in ln)]
        text_rows = [i for i, ln in enumerate(lines) if spans_columns(ln) and i not in anchors]
        # Várias linhas só de texto sem régua: na 1ª faixa é cabeçalho de várias linhas; fora dela, ambíguo
        if b_idx > 0 and len(text_rows) >= 2 and len(anchors) < 2:
            return PageTable(bbox, 'linhas sem separação confiável')
        if len(anchors) >= 2 and any(i not in anchors for i in range(anchors[1], len(lines))):
            return PageTable(bbox, 'linhas sem separação confiável')
        groups: List[List[_Word]] = []
        pending: List[_Word] = []
        for i, ln in enumerate(lines):
            if len(anchors) >= 2 and i in anchors:
                groups.append(pending + ln)
                pending = []
            elif groups:
                groups[-1].extend(ln)
            else:
                pending.extend(ln)
        if pending:
            groups.append(pending)
        for grp in groups:
            y0, y1 = min(w.y0 for w in grp), max(w.y1 for w in grp)
            # Fronteiras ativas nesta linha: cruzadas por régua ou não atravessadas por texto (senão, colspan)
            active = [b for b in bounds if rule_crosses(b, y0, y1) or not any(w.x0 + 1 < b < w.x1 - 1 for w in grp)]
            cells: List[List[_Word]] = [[] for _ in range(ncols)]
            for w in grp:
                seg = sum(1 for b in active if w.cx > b)
                left = active[seg - 1] if seg > 0 else None
                cells[col_of(left + 0.01) if left is not None else 0].append(w)
            rows.append([_cell_text(c) for c in cells])

    keep = [j for j in range(ncols) if any(r[j] for r in rows)]
    rows = [[r[j] for j in keep] for r in rows]

    if len(rows) < 2 or len(keep) < 2:
        return PageTable(bbox, 'degenerada')
    cells = [c for i, r in enumerate(rows) for j, c in enumerate(r) if (i, j) != (0, 0)]
    if sum(1 for c in cells if not c) / len(cells) > MAX_EMPTY_CELL_RATIO:
        return PageTable(bbox, 'células vazias (rowspan/colspan/gráfico)', caption, rows)
    if any(MERGED_NUMBERS_REGEX.match(c) for r in rows[1:] for c in r):
        return PageTable(bbox, 'linhas fundidas', caption, rows)
    return PageTable(bbox, TABLE_STATUS_OK, caption, rows)


def extract_page_tables(page: pymupdf.Page) -> List[PageTable]:
    """
    Detecta as tabelas da página via find_tables() e estrutura cada uma.
    Retorna todas as detecções (aprovadas e rejeitadas), pois as rejeitadas
    continuam relevantes para a detecção de imagens e a proteção de frações.
    """
    try:
        found = page.find_tables().tables
    except Exception:
        return []
    found = [t for t in found if t.row_count >= 2 and t.col_count >= 2]
    if not found:
        return []
    drawings = page.get_drawings()
    page_words = _page_words(page)
    tables = []
    for t in found:
        # Linhas sobrepostas indicam célula de várias linhas (rowspan): fronteiras internas a outra
        # linha não separam linhas da tabela (ex.: cabeçalho de três linhas ao lado de subdivisões)
        spans = [(r.bbox[1], r.bbox[3]) for r in t.rows]
        row_ys = [y for y0, y1 in spans for y in (y0, y1)
                  if not any(a + 1 < y < b - 1 for a, b in spans)]
        try:
            tables.append(extract_table(pymupdf.Rect(t.bbox), drawings, page_words, row_ys))
        except Exception as e:
            tables.append(PageTable(pymupdf.Rect(t.bbox), f'erro: {e}'))
    return tables
