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
    QUESTION_SPLIT_REGEX,
    ALT_LINE_REGEX,
    IMAGE_ALT_PLACEHOLDER
)

def clean_page_text(text: str) -> str:
    """
    Remove marcas d'água, códigos de barras e cabeçalhos/rodapés repetitivos da página,
    unificando números de questões quebrados em linhas distintas.
    """
    # 1. Unifica 'Questão \n 14' em 'Questão 14' antes de qualquer filtro de linhas
    text = re.sub(r'(QUEST[ÃA]O)\s*[\n\r]+\s*(\d+)', r'\1 \2', text, flags=re.IGNORECASE)

    # 2. Remove marcas d'água do tipo ENEM2024ENEM2024... ou com variações/erros como ENEM20E4
    text = re.sub(r'(ENEM\s*20[0-9A-Z]{2}\s*){2,}', '', text, flags=re.IGNORECASE)
    # Remove códigos de barras *020325AZ2*
    text = BARCODE_REGEX.sub('', text)

    lines = []
    for line in text.split('\n'):
        s = line.strip()
        # Rodapé com menção a caderno ou dia
        if re.search(r'CADERNO\s+\d+', s, re.IGNORECASE) and any(c in s.upper() for c in ['AZUL', 'AMARELO', 'VERDE', 'BRANCO', 'CINZA', 'ROSA', 'PÁGINA', 'PAGINA']):
            continue
        # Números de página isolados
        if re.match(r'^\d{1,2}$', s):
            continue
        # Cabeçalhos ou rodapés com nome da área e dia (por extenso ou siglas CH, CN, LC, MT, RED)
        if RUNNING_AREA_DAY_REGEX.search(s):
            continue
        lines.append(line)

    return '\n'.join(lines)

def parse_question_body(q_text: str) -> Tuple[str, Dict[str, str]]:
    """
    Segmenta o corpo de uma questão em enunciado e alternativas A, B, C, D, E.
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

            if not alt_content:
                alt_content = IMAGE_ALT_PLACEHOLDER
            alts[let] = alt_content

        clean_enunciado = " ".join(enunciado_raw.split())
        return clean_enunciado, alts
    else:
        clean_enunciado = " ".join(q_text.split())
        return clean_enunciado, {}

def detect_images_per_question(doc: pymupdf.Document, has_duplicate_languages: bool) -> Set[Tuple[int, Optional[float]]]:
    """
    Identifica quais questões no documento PDF contêm imagens/figuras através de coordenadas espaciais.
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

            img_col = 0 if b[0] < mid_x else 1
            img_y_mid = (b[1] + b[3]) / 2.0

            for r in q_regions:
                if r['page'] == page_num and r['col'] == img_col:
                    if (r['y0'] - 20) <= img_y_mid <= (r['y1'] + 20):
                        questions_with_images.add((r['num'], r['lang']))
                        break

    return questions_with_images

def extract_questions_from_pdf(pdf_path: Path) -> Dict[Tuple[int, Optional[float]], Dict[str, Any]]:
    """
    Extrai todas as questões de um caderno PDF, retornando um dicionário indexado por (número_questão, língua).
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")

    doc = pymupdf.open(pdf_path)

    # Extrai e limpa o texto das páginas
    pages_text = [clean_page_text(doc[p].get_text("text")) for p in range(1, len(doc))]
    full_text = "\n".join(pages_text)

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

        # Determina se a questão contém imagem
        has_img_in_alts = any(val == IMAGE_ALT_PLACEHOLDER for val in alts.values())
        has_spatial_img = (q_num, lang) in questions_with_spatial_images
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
