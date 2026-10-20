"""
Módulo para mapeamento determinístico dos arquivos PDF de prova utilizando
identificação dinâmica de conteúdo (Fingerprinting) e o catálogo oficial como fallback.
Aplica a regra de escopo: seleciona exatamente 1 cor de prova regular (P1) e 1 cor de prova
de reaplicação/PPL (P2) por edição para a área informada (MT, CN, CH ou LC).
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

from src.catalog import get_pdf_filename, normalize_color
from src.config import PREFERRED_COLORS, get_day_for_area
from src.pdf_fingerprint import scan_provas_directory


def find_pdf_in_dir(provas_dir: Path, target_filename: str) -> Optional[Path]:
    """
    Localiza o arquivo PDF no diretório de provas de forma insensível a maiúsculas/minúsculas,
    pesquisando inicialmente no diretório raiz e recursivamente em subpastas caso necessário.
    Suporta variações de extensão como .pdf e .pdf.pdf (comum no acervo oficial de 2015).
    """
    target_lower = target_filename.lower()
    variants = {target_lower}
    if target_lower.endswith('.pdf.pdf'):
        variants.add(target_lower[:-4])
    elif target_lower.endswith('.pdf'):
        variants.add(target_lower + '.pdf')

    # 1. Busca direta no diretório de provas
    for file_path in provas_dir.glob("*.pdf"):
        if file_path.name.lower() in variants:
            return file_path
    for file_path in provas_dir.glob("*.PDF"):
        if file_path.name.lower() in variants:
            return file_path

    # 2. Busca recursiva (útil para anos como 2017 com subpastas P1/02_Domingo...)
    for file_path in provas_dir.rglob("*.pdf"):
        if file_path.name.lower() in variants:
            return file_path
    for file_path in provas_dir.rglob("*.PDF"):
        if file_path.name.lower() in variants:
            return file_path

    return None


def build_selected_exams(
    provas_dir: Path,
    df_dict: pd.DataFrame,
    year: int,
    area: str = 'MT'
) -> Dict[int, Dict[str, Any]]:
    """
    Executa a seleção unária determinística de cadernos de prova para uma área específica (MT, CN, CH ou LC):
    1. Determina o dia da prova correspondente à área e ano via get_day_for_area.
    2. Inspeciona o conteúdo dos PDFs em provas_dir (Fingerprinting da folha de rosto).
    3. Seleciona 1 cor de Primeira Aplicação Regular (P1).
    4. Seleciona 1 cor de Reaplicação / PPL (P2) se disponível no dicionário e no acervo.
    5. Utiliza o catálogo estático oficial como fallback de segurança.

    Retorna um dicionário:
    {
        CO_PROVA: {
            'pdf_path': Path,
            'tp_aplicacao': 'REGULAR' ou 'REAPLICACAO_PPL',
            'app_key': 'P1' ou 'P2',
            'tx_cor': str,
            'desc_original': str,
            'day': int,
            'area': str
        }
    }
    """
    if not provas_dir.exists():
        raise FileNotFoundError(f"Diretório de provas não encontrado em: {provas_dir}")

    area_upper = area.upper().strip()
    day = get_day_for_area(area_upper, year)
    selected: Dict[int, Dict[str, Any]] = {}

    # Inspeciona dinamicamente os PDFs da pasta de provas via fingerprinting
    fingerprinted_exams = scan_provas_directory(provas_dir)
    fp_map: Dict[Tuple[int, str, str], List[Path]] = {}
    for item in fingerprinted_exams:
        key = (item['day'], item['app'], item['color'])
        fp_map.setdefault(key, []).append(item['path'])

    # 1. Seleciona 1 Caderno Regular (P1)
    df_p1 = df_dict[df_dict['TP_APLICACAO'] == 'P1']
    p1_chosen = False

    for color in PREFERRED_COLORS:
        matching_rows = df_p1[df_p1['TX_COR'] == color]
        if matching_rows.empty:
            continue

        for _, row in matching_rows.iterrows():
            co_prova = int(row['CO_PROVA'])
            pdf_path = None

            # 1a. Tenta via Fingerprinting de conteúdo (filtrando pelo dia exato)
            fp_key = (day, 'P1', color)
            if fp_key in fp_map and fp_map[fp_key]:
                expected_filename = get_pdf_filename(year, day, color, application='P1')
                candidates = fp_map[fp_key]
                if expected_filename:
                    match_cand = [p for p in candidates if p.name.lower() == expected_filename.lower()]
                    pdf_path = match_cand[0] if match_cand else candidates[0]
                else:
                    pdf_path = candidates[0]

            # 1b. Fallback via Catálogo estático e busca por nome de arquivo
            if not pdf_path:
                expected_filename = get_pdf_filename(year, day, color, application='P1')
                if expected_filename:
                    found = find_pdf_in_dir(provas_dir, expected_filename)
                    if found and found.exists():
                        pdf_path = found

            if pdf_path and pdf_path.exists():
                selected[co_prova] = {
                    'pdf_path': pdf_path,
                    'tp_aplicacao': 'REGULAR',
                    'app_key': 'P1',
                    'tx_cor': color,
                    'desc_original': row.get('DESC_ORIGINAL', ''),
                    'day': day,
                    'area': area_upper
                }
                p1_chosen = True
                break

        if p1_chosen:
            break

    # Fallback para P1 se nenhuma das cores preferidas funcionou: pega qualquer cor de P1 disponível
    if not p1_chosen:
        for _, row in df_p1.iterrows():
            co_prova = int(row['CO_PROVA'])
            color = str(row['TX_COR']).strip()
            pdf_path = None

            fp_key = (day, 'P1', color)
            if fp_key in fp_map and fp_map[fp_key]:
                pdf_path = fp_map[fp_key][0]
            else:
                expected_filename = get_pdf_filename(year, day, color, application='P1')
                if expected_filename:
                    found = find_pdf_in_dir(provas_dir, expected_filename)
                    if found and found.exists():
                        pdf_path = found

            if pdf_path and pdf_path.exists():
                selected[co_prova] = {
                    'pdf_path': pdf_path,
                    'tp_aplicacao': 'REGULAR',
                    'app_key': 'P1',
                    'tx_cor': color,
                    'desc_original': row.get('DESC_ORIGINAL', ''),
                    'day': day,
                    'area': area_upper
                }
                break

    # 2. Seleciona 1 Caderno de Reaplicação / PPL (P2)
    df_p2 = df_dict[df_dict['TP_APLICACAO'] == 'P2']
    p2_chosen = False

    for color in PREFERRED_COLORS:
        matching_rows = df_p2[df_p2['TX_COR'] == color]
        if matching_rows.empty:
            continue

        for _, row in matching_rows.iterrows():
            co_prova = int(row['CO_PROVA'])
            pdf_path = None

            # 2a. Tenta via Fingerprinting de conteúdo
            fp_key = (day, 'P2', color)
            if fp_key in fp_map and fp_map[fp_key]:
                expected_filename = get_pdf_filename(year, day, color, application='P2')
                candidates = fp_map[fp_key]
                if expected_filename:
                    match_cand = [p for p in candidates if p.name.lower() == expected_filename.lower()]
                    pdf_path = match_cand[0] if match_cand else candidates[0]
                else:
                    pdf_path = candidates[0]

            # 2b. Fallback via Catálogo estático
            if not pdf_path:
                expected_filename = get_pdf_filename(year, day, color, application='P2')
                if expected_filename:
                    found = find_pdf_in_dir(provas_dir, expected_filename)
                    if found and found.exists():
                        pdf_path = found

            if pdf_path and pdf_path.exists():
                selected[co_prova] = {
                    'pdf_path': pdf_path,
                    'tp_aplicacao': 'REAPLICACAO_PPL',
                    'app_key': 'P2',
                    'tx_cor': color,
                    'desc_original': row.get('DESC_ORIGINAL', ''),
                    'day': day,
                    'area': area_upper
                }
                p2_chosen = True
                break

        if p2_chosen:
            break

    # Fallback para P2 se nenhuma das preferidas funcionou
    if not p2_chosen and not df_p2.empty:
        for _, row in df_p2.iterrows():
            co_prova = int(row['CO_PROVA'])
            color = str(row['TX_COR']).strip()
            pdf_path = None

            fp_key = (day, 'P2', color)
            if fp_key in fp_map and fp_map[fp_key]:
                pdf_path = fp_map[fp_key][0]
            else:
                expected_filename = get_pdf_filename(year, day, color, application='P2')
                if expected_filename:
                    found = find_pdf_in_dir(provas_dir, expected_filename)
                    if found and found.exists():
                        pdf_path = found

            if pdf_path and pdf_path.exists():
                selected[co_prova] = {
                    'pdf_path': pdf_path,
                    'tp_aplicacao': 'REAPLICACAO_PPL',
                    'app_key': 'P2',
                    'tx_cor': color,
                    'desc_original': row.get('DESC_ORIGINAL', ''),
                    'day': day,
                    'area': area_upper
                }
                break

    return selected


def build_selected_math_exams(
    provas_dir: Path,
    df_dict_math: pd.DataFrame,
    year: int
) -> Dict[int, Dict[str, Any]]:
    """
    Função de compatibilidade: invoca build_selected_exams para Matemática (MT).
    """
    return build_selected_exams(provas_dir, df_dict_math, year, area='MT')


def build_math_exam_pdf_mapping(
    provas_dir: Path,
    df_dict_math: pd.DataFrame,
    year: int
) -> Dict[int, Path]:
    """
    Retorna mapeamento CO_PROVA -> Path_do_PDF para Matemática.
    """
    detailed_map = build_selected_math_exams(provas_dir, df_dict_math, year)
    return {co_prova: info['pdf_path'] for co_prova, info in detailed_map.items()}


def build_exam_pdf_mapping(provas_dir: Path, df_itens: pd.DataFrame, year: int) -> Dict[int, Path]:
    """
    Função legada para mapeamento direto via colunas do CSV de itens.
    """
    if not provas_dir.exists():
        raise FileNotFoundError(f"Diretório de provas não encontrado em: {provas_dir}")

    exam_groups = df_itens[['CO_PROVA', 'SG_AREA', 'TX_COR']].dropna().drop_duplicates()

    if 'IN_ITEM_ADAPTADO' in df_itens.columns:
        adapted_exams = set(df_itens[df_itens['IN_ITEM_ADAPTADO'] == 1]['CO_PROVA'].unique())
    else:
        adapted_exams = set()

    mapping: Dict[int, Path] = {}

    for _, row in exam_groups.iterrows():
        try:
            co_prova = int(row['CO_PROVA'])
        except (ValueError, TypeError):
            continue

        if co_prova in adapted_exams:
            continue

        area = str(row['SG_AREA']).strip().upper()
        color = str(row['TX_COR']).strip()

        try:
            day = get_day_for_area(area, year)
        except ValueError:
            continue

        expected_filename = get_pdf_filename(year, day, color, application='P1')
        if not expected_filename:
            continue

        pdf_path = find_pdf_in_dir(provas_dir, expected_filename)
        if pdf_path and pdf_path.exists():
            mapping[co_prova] = pdf_path

    return mapping
