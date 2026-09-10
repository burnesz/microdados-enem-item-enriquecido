"""
Módulo para mapeamento determinístico dos arquivos PDF de prova utilizando o catálogo oficial.
"""

from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from src.catalog import get_pdf_filename, normalize_color
from src.config import get_day_for_area

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

def build_math_exam_pdf_mapping(provas_dir: Path, df_dict_math: pd.DataFrame, year: int) -> Dict[int, Path]:
    """
    Constrói o mapeamento CO_PROVA -> Caminho do PDF do caderno para a área de Matemática,
    cruzando os pares (CO_PROVA, TX_COR) obtidos dinamicamente do Dicionário de Dados
    com o Catálogo Estático Oficial de PDFs (sempre Dia 2).
    """
    if not provas_dir.exists():
        raise FileNotFoundError(f"Diretório de provas não encontrado em: {provas_dir}")

    mapping: Dict[int, Path] = {}
    day = 2  # Prova de Matemática ocorre invariavelmente no Dia 2

    for _, row in df_dict_math.iterrows():
        try:
            co_prova = int(row['CO_PROVA'])
        except (ValueError, TypeError):
            continue

        color = str(row['TX_COR']).strip()
        expected_filename = get_pdf_filename(year, day, color)
        if not expected_filename:
            continue

        pdf_path = find_pdf_in_dir(provas_dir, expected_filename)
        if pdf_path and pdf_path.exists():
            mapping[co_prova] = pdf_path

    return mapping

def build_exam_pdf_mapping(provas_dir: Path, df_itens: pd.DataFrame, year: int) -> Dict[int, Path]:
    """
    Constrói o dicionário mapeando CO_PROVA -> Caminho do PDF do caderno,
    utilizando as colunas CO_PROVA, SG_AREA e TX_COR do CSV de itens e o catálogo estático.
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

        expected_filename = get_pdf_filename(year, day, color)
        if not expected_filename:
            continue

        pdf_path = find_pdf_in_dir(provas_dir, expected_filename)
        if pdf_path and pdf_path.exists():
            mapping[co_prova] = pdf_path

    return mapping
