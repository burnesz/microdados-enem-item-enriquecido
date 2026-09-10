"""
Módulo para mapeamento determinístico dos arquivos PDF de prova utilizando o catálogo oficial.
Aplica a regra de escopo: seleciona exatamente 1 cor de prova regular (P1) e 1 cor de prova
de reaplicação/PPL (P2) por edição de Matemática.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

from src.catalog import get_pdf_filename, normalize_color
from src.config import PREFERRED_COLORS, get_day_for_area

def find_pdf_in_dir(provas_dir: Path, target_filename: str) -> Optional[Path]:
    """
    Localiza o arquivo PDF no diretório de provas de forma insensível a maiúsculas/minúsculas,
    pesquisando inicialmente no diretório raiz e recursivamente em subpastas caso necessário.
    """
    target_lower = target_filename.lower()

    # 1. Busca direta no diretório de provas
    for file_path in provas_dir.glob("*.pdf"):
        if file_path.name.lower() == target_lower:
            return file_path
    for file_path in provas_dir.glob("*.PDF"):
        if file_path.name.lower() == target_lower:
            return file_path

    # 2. Busca recursiva (útil para anos como 2017 com subpastas P1/02_Domingo...)
    for file_path in provas_dir.rglob("*.pdf"):
        if file_path.name.lower() == target_lower:
            return file_path
    for file_path in provas_dir.rglob("*.PDF"):
        if file_path.name.lower() == target_lower:
            return file_path

    return None

def build_math_exam_pdf_mapping(
    provas_dir: Path,
    df_dict_math: pd.DataFrame,
    year: int
) -> Dict[int, Path]:
    """
    Seleciona deterministicamente exatamente 1 cor de caderno regular (P1)
    e 1 cor de caderno de reaplicação/PPL (P2) para a área de Matemática (Dia 2).

    Retorna um dicionário mapeando CO_PROVA -> Path_do_PDF_Fisico.
    """
    detailed_map = build_selected_math_exams(provas_dir, df_dict_math, year)
    return {co_prova: info['pdf_path'] for co_prova, info in detailed_map.items()}

def build_selected_math_exams(
    provas_dir: Path,
    df_dict_math: pd.DataFrame,
    year: int
) -> Dict[int, Dict[str, Any]]:
    """
    Executa a seleção unária determinística de cadernos de prova para Matemática (Dia 2):
    1. Seleciona 1 cor de Primeira Aplicação Regular (P1).
    2. Seleciona 1 cor de Reaplicação / PPL (P2) se disponível no dicionário e no acervo.

    Retorna um dicionário:
    {
        CO_PROVA: {
            'pdf_path': Path,
            'tp_aplicacao': 'REGULAR' ou 'REAPLICACAO_PPL',
            'app_key': 'P1' ou 'P2',
            'tx_cor': str,
            'desc_original': str
        }
    }
    """
    if not provas_dir.exists():
        raise FileNotFoundError(f"Diretório de provas não encontrado em: {provas_dir}")

    selected: Dict[int, Dict[str, Any]] = {}
    day = 2  # Matemática ocorre sempre no Dia 2

    # 1. Seleciona 1 Caderno Regular (P1)
    df_p1 = df_dict_math[df_dict_math['TP_APLICACAO'] == 'P1']
    p1_chosen = False

    for color in PREFERRED_COLORS:
        matching_rows = df_p1[df_p1['TX_COR'] == color]
        if matching_rows.empty:
            continue

        for _, row in matching_rows.iterrows():
            co_prova = int(row['CO_PROVA'])
            expected_filename = get_pdf_filename(year, day, color, application='P1')
            if not expected_filename:
                continue

            pdf_path = find_pdf_in_dir(provas_dir, expected_filename)
            if pdf_path and pdf_path.exists():
                selected[co_prova] = {
                    'pdf_path': pdf_path,
                    'tp_aplicacao': 'REGULAR',
                    'app_key': 'P1',
                    'tx_cor': color,
                    'desc_original': row.get('DESC_ORIGINAL', '')
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
            expected_filename = get_pdf_filename(year, day, color, application='P1')
            if not expected_filename:
                continue
            pdf_path = find_pdf_in_dir(provas_dir, expected_filename)
            if pdf_path and pdf_path.exists():
                selected[co_prova] = {
                    'pdf_path': pdf_path,
                    'tp_aplicacao': 'REGULAR',
                    'app_key': 'P1',
                    'tx_cor': color,
                    'desc_original': row.get('DESC_ORIGINAL', '')
                }
                break

    # 2. Seleciona 1 Caderno de Reaplicação / PPL (P2)
    df_p2 = df_dict_math[df_dict_math['TP_APLICACAO'] == 'P2']
    p2_chosen = False

    for color in PREFERRED_COLORS:
        matching_rows = df_p2[df_p2['TX_COR'] == color]
        if matching_rows.empty:
            continue

        for _, row in matching_rows.iterrows():
            co_prova = int(row['CO_PROVA'])
            expected_filename = get_pdf_filename(year, day, color, application='P2')
            if not expected_filename:
                continue

            pdf_path = find_pdf_in_dir(provas_dir, expected_filename)
            if pdf_path and pdf_path.exists():
                selected[co_prova] = {
                    'pdf_path': pdf_path,
                    'tp_aplicacao': 'REAPLICACAO_PPL',
                    'app_key': 'P2',
                    'tx_cor': color,
                    'desc_original': row.get('DESC_ORIGINAL', '')
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
            expected_filename = get_pdf_filename(year, day, color, application='P2')
            if not expected_filename:
                continue
            pdf_path = find_pdf_in_dir(provas_dir, expected_filename)
            if pdf_path and pdf_path.exists():
                selected[co_prova] = {
                    'pdf_path': pdf_path,
                    'tp_aplicacao': 'REAPLICACAO_PPL',
                    'app_key': 'P2',
                    'tx_cor': color,
                    'desc_original': row.get('DESC_ORIGINAL', '')
                }
                break

    return selected

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
