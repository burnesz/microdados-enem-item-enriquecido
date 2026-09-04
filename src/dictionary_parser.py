"""
Módulo para leitura e interpretação do Dicionário de Dados do ENEM.
"""

from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from src.config import EXCLUDED_TEST_KEYWORDS, REGULAR_COLORS

def parse_dictionary(dictionary_path: Path, year: int) -> pd.DataFrame:
    """
    Lê o dicionário de microdados (.xlsx) e extrai o mapeamento de CO_PROVA
    para cada Área do Conhecimento e Cor de Caderno regular.
    """
    if not dictionary_path.exists():
        raise FileNotFoundError(f"Dicionário não encontrado em: {dictionary_path}")

    # Identifica a aba correspondente a RESULTADOS
    excel_file = pd.ExcelFile(dictionary_path)
    target_sheet = None
    for sheet in excel_file.sheet_names:
        if "RESULTADOS" in sheet.upper():
            target_sheet = sheet
            break

    if not target_sheet:
        raise ValueError(f"Aba de resultados não encontrada no dicionário: {excel_file.sheet_names}")

    df_dict = pd.read_excel(dictionary_path, sheet_name=target_sheet)

    area_cols = ['CO_PROVA_CN', 'CO_PROVA_CH', 'CO_PROVA_LC', 'CO_PROVA_MT']
    records = []
    curr_area = None

    for _, row in df_dict.iterrows():
        val_col0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

        # Verifica se inicia uma nova variável de prova
        for ac in area_cols:
            if ac in val_col0:
                curr_area = ac.replace('CO_PROVA_', '')
                break

        if curr_area:
            val_code = row.iloc[2]
            val_desc = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""

            try:
                code = int(val_code)
                desc_lower = val_desc.lower()

                # Verifica se é prova regular (não adaptada e não reaplicação)
                is_excluded = any(kw in desc_lower for kw in EXCLUDED_TEST_KEYWORDS)

                # Identifica cor padronizada
                standard_color = None
                for col in REGULAR_COLORS:
                    if desc_lower.startswith(col.lower()) or desc_lower == col.lower():
                        standard_color = col
                        break

                if not is_excluded and standard_color is not None:
                    records.append({
                        'SG_AREA': curr_area,
                        'CO_PROVA': code,
                        'TX_COR': standard_color,
                        'DESC_ORIGINAL': val_desc,
                        'IS_REGULAR': True
                    })
            except (ValueError, TypeError):
                # Se mudou de variável (linha não vazia na primeira coluna), reseta
                if pd.notna(row.iloc[0]) and not any(ac in str(row.iloc[0]) for ac in area_cols):
                    curr_area = None

    result_df = pd.DataFrame(records)
    if result_df.empty:
        raise RuntimeError(f"Nenhum código de prova regular encontrado no dicionário para o ano {year}.")

    return result_df
