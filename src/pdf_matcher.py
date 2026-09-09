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
    Localiza o arquivo PDF no diretório de provas de forma insensível a maiúsculas/minúsculas.
    """
    target_lower = target_filename.lower()
    for file_path in provas_dir.glob("*.pdf"):
        if file_path.name.lower() == target_lower:
            return file_path
    for file_path in provas_dir.glob("*.PDF"):
        if file_path.name.lower() == target_lower:
            return file_path
    return None

def build_exam_pdf_mapping(provas_dir: Path, df_itens: pd.DataFrame, year: int) -> Dict[int, Path]:
    """
    Constrói o dicionário mapeando CO_PROVA -> Caminho do PDF do caderno,
    utilizando as colunas CO_PROVA, SG_AREA e TX_COR do CSV de itens e o catálogo estático.
    """
    if not provas_dir.exists():
        raise FileNotFoundError(f"Diretório de provas não encontrado em: {provas_dir}")

    # Agrupa por CO_PROVA para obter a combinação única de prova, área e cor
    exam_groups = df_itens[['CO_PROVA', 'SG_AREA', 'TX_COR']].dropna().drop_duplicates()

    # Se a coluna IN_ITEM_ADAPTADO estiver presente, exclui provas adaptadas
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
            # Prova com cor não regular ou sem caderno mapeado
            continue

        pdf_path = find_pdf_in_dir(provas_dir, expected_filename)
        if pdf_path and pdf_path.exists():
            mapping[co_prova] = pdf_path

    return mapping
