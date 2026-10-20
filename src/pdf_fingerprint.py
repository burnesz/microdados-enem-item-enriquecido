"""
Módulo de identificação dinâmica de cadernos de prova do ENEM via inspeção de conteúdo (Fingerprinting).

Inspeciona a primeira página (folha de rosto) dos arquivos PDF com PyMuPDF para extrair:
- Dia da Prova (Dia 2 / Matemática)
- Tipo de Aplicação (Regular / P1 vs Reaplicação/PPL / P2)
- Cor padronizada do caderno (AMARELO, AZUL, CINZA, ROSA, BRANCO, VERDE)

Permite casar arquivos PDF independentemente de variações no nome de arquivo físico ou
de subpastas onde estejam alocados.
"""

from pathlib import Path
import re
from typing import Dict, List, Optional, Any
import pymupdf

from src.catalog import normalize_color

# Palavras-chave no nome do arquivo que descartam documentos técnicos não-prova
NON_EXAM_KEYWORDS = [
    'EDITAL', 'MANUAL', 'MATRIZ', 'QUESTIONARIO', 'QUESTIONÁRIO',
    'RELATORIO', 'RELATÓRIO', 'PROCEDIMENTOS', 'ENTENDA', 'GUIA',
    'RASCUNHO', 'INSTRUCOES', 'INSTRUÇÕES'
]

# Palavras-chave de provas adaptadas ou digitais que devem ser excluídas do escopo
ADAPTED_KEYWORDS = [
    'BRAILE', 'LIBRAS', 'AMPLIADA', 'SUPERAMPLIADA', 'DOSVOX', 'NVDA', 'DIGITAL'
]

# Cores regulares reconhecidas
SUPPORTED_COLORS = ['AMARELO', 'AMARELA', 'AZUL', 'CINZA', 'ROSA', 'BRANCO', 'BRANCA', 'VERDE']


def inspect_exam_pdf(pdf_path: Path) -> Optional[Dict[str, Any]]:
    """
    Inspeciona um arquivo PDF para determinar se é um caderno de prova de Matemática (Dia 2),
    identificando a aplicação (P1 vs P2) e a cor da capa.

    Retorna um dicionário com os metadados extraídos ou None se não for caderno válido de Matemática.
    """
    if not pdf_path.is_file():
        return None

    name_upper = pdf_path.name.upper()
    parent_upper = pdf_path.parent.name.upper()

    # 1. Filtro rápido de exclusão por nome de documento técnico
    if any(kw in name_upper for kw in NON_EXAM_KEYWORDS):
        return None

    # 2. Exclusão de provas adaptadas e digitais
    if any(kw in name_upper for kw in ADAPTED_KEYWORDS):
        return None

    # Exceção histórica conhecida de 2011: P1 Dia 2 foi publicado como CINZA_LEDOR pelo INEP
    if 'LEDOR' in name_upper and not ('2011' in name_upper and 'CAD_06' in name_upper):
        return None

    # 3. Abertura do PDF e validação de quantidade de páginas
    # Cadernos completos do ENEM possuem de 16 a 36 páginas; gabaritos avulsos têm de 1 a 2 páginas.
    try:
        doc = pymupdf.open(pdf_path)
    except Exception:
        return None

    page_count = len(doc)
    if page_count < 10:
        doc.close()
        return None

    # Lê o texto da folha de rosto (página 1; página 2 se a página 1 for muito curta)
    cover_text = doc[0].get_text('text')
    if page_count > 1 and len(cover_text.strip()) < 80:
        cover_text += '\n' + doc[1].get_text('text')
    doc.close()

    cover_upper = cover_text.upper()

    # Verifica adaptações também no corpo da folha de rosto
    if any(kw in cover_upper for kw in ['SUPERAMPLIADA', 'AMPLIADA', 'LIBRAS', 'BRAILE']):
        return None

    # 4. Verificação de Dia 2 / Área de Matemática
    is_dia2 = False
    if any(k in name_upper for k in ['DIA_2', 'DIA2', 'DOM', 'D2', 'CAD_05', 'CAD_06', 'CAD_07', 'CAD_08', 'CADERNO5', 'CADERNO6', 'CADERNO7', 'CADERNO8']):
        is_dia2 = True
    elif re.search(r'2\s*[º°ªoO]?\s*DIA', cover_upper) or 'DOMINGO' in cover_upper or 'MATEMÁTICA' in cover_upper:
        is_dia2 = True

    if not is_dia2:
        return None

    # 5. Verificação da Aplicação (P1 vs P2 / Reaplicação / PPL)
    is_p2 = False
    if 'SEGUNDA APLICAÇÃO' in parent_upper or 'SEGUNDA APLICACAO' in parent_upper or 'P2' in parent_upper:
        is_p2 = True
    elif any(k in name_upper for k in ['_P2_', '_2.PDF', '_2.PDF.PDF', 'PPL', '2_APLICAÇÃO', '2_APLICACAO', '_P2.PDF', '_P2_CAD']):
        is_p2 = True
    elif re.search(r'2\s*[ªº°aA]?\s*APLICA[ÇC][ÃA]O', cover_upper) or 'REAPLICAÇÃO' in cover_upper or 'REAPLICACAO' in cover_upper or 'PPL' in cover_upper:
        is_p2 = True

    app = 'P2' if is_p2 else 'P1'

    # 6. Identificação da Cor
    detected_color = None

    # Primeiro tenta extrair do nome do arquivo
    for c in SUPPORTED_COLORS:
        if c in name_upper:
            detected_color = normalize_color(c)
            break

    # Se não encontrado no nome, extrai das frases padronizadas da folha de rosto
    if not detected_color:
        for c in SUPPORTED_COLORS:
            patterns = [
                f'CADERNO {c}',
                f'CADERNO DE QUESTÕES É {c}',
                f'CADERNO DE QUESTOES E {c}',
                f'CAPA DO SEU CADERNO DE QUESTÕES É {c}',
                f'CAPA DO SEU CADERNO DE QUESTOES E {c}',
                f'– {c}',
                f'- {c}',
            ]
            if any(p in cover_upper for p in patterns):
                detected_color = normalize_color(c)
                break

    if not detected_color:
        return None

    return {
        'path': pdf_path,
        'app': app,
        'color': detected_color,
        'day': 2,
        'pages': page_count
    }


def scan_provas_directory(provas_dir: Path) -> List[Dict[str, Any]]:
    """
    Percorre recursivamente a pasta de provas, inspeciona todos os arquivos PDF
    e retorna uma lista de cadernos válidos de Matemática identificados.
    """
    if not provas_dir.exists():
        return []

    candidates: List[Dict[str, Any]] = []
    seen_paths = set()

    for ext in ("*.pdf", "*.PDF"):
        for p in provas_dir.rglob(ext):
            p_resolved = p.resolve()
            if p_resolved in seen_paths:
                continue
            seen_paths.add(p_resolved)

            info = inspect_exam_pdf(p)
            if info:
                candidates.append(info)

    return candidates
