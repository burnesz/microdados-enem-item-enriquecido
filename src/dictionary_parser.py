"""
Módulo para leitura e interpretação do Dicionário de Dados do ENEM.
Realiza busca dinâmica pelo atributo CO_PROVA_MT em todas as abas da planilha,
classificando as provas identificadas em Primeira Aplicação (P1) e Reaplicação/PPL (P2),
e descartando provas adaptadas e digitais. Trata omissões históricas conhecidas nos dicionários do INEP.
"""

from pathlib import Path
from typing import Dict, List, Optional
import openpyxl
import pandas as pd

from src.catalog import normalize_color
from src.config import ADAPTED_TEST_KEYWORDS, PPL_TEST_KEYWORDS, REGULAR_COLORS, TARGET_AREA

# Mapeamento de códigos de provas de Matemática omitidos nas planilhas oficiais de Dicionário do INEP
KNOWN_DICTIONARY_OMISSIONS = {
    # 2011: O dicionário do INEP omitiu na variável CO_PROVA_MT a prova de Reaplicação / PPL (código 136, Cinza)
    136: {
        'SG_AREA': TARGET_AREA,
        'CO_PROVA': 136,
        'TX_COR': 'CINZA',
        'TP_APLICACAO': 'P2',
        'DESC_ORIGINAL': 'Cinza (Reaplicação / PPL)'
    }
}

def parse_math_exam_codes(
    dictionary_path: Path,
    csv_path: Optional[Path] = None
) -> pd.DataFrame:
    """
    Percorre dinamicamente todas as abas do dicionário de dados (.xlsx), localizando
    a célula que contém a variável 'CO_PROVA_MT'. A partir dessa linha, extrai os códigos
    numéricos de prova, descrições e cores, classificando em P1 (Regular) e P2 (Reaplicação / PPL)
    e descartando provas adaptadas e digitais.

    Caso fornecido 'csv_path', reconcilia e incorpora códigos válidos de Matemática presentes
    no CSV que foram omitidos na planilha oficial do Dicionário (ex: código 136 em 2011).

    Retorna um DataFrame contendo as colunas:
    - SG_AREA: 'MT'
    - CO_PROVA: int (código da prova)
    - TX_COR: str (cor padronizada, ex: 'AZUL', 'AMARELO', 'CINZA', 'ROSA', 'VERDE')
    - TP_APLICACAO: str ('P1' para Regular ou 'P2' para Reaplicação/PPL)
    - DESC_ORIGINAL: str (descrição original no dicionário)
    """
    if not dictionary_path.exists():
        raise FileNotFoundError(f"Dicionário não encontrado em: {dictionary_path}")

    wb = openpyxl.load_workbook(dictionary_path, read_only=True, data_only=True)
    records = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))

        target_row_idx = None
        for r_idx, row in enumerate(rows):
            if any(cell and 'CO_PROVA_MT' in str(cell).strip().upper() for cell in row):
                target_row_idx = r_idx
                break

        if target_row_idx is None:
            continue

        # Itera pelas linhas a partir da posição da variável
        for r_idx in range(target_row_idx, len(rows)):
            row = rows[r_idx]
            if not row or all(v is None for v in row):
                continue

            # Se ultrapassou a linha inicial e começou uma nova variável (CO_, TX_, TP_, IN_, NU_, SG_)
            if r_idx > target_row_idx:
                first_val = next((c for c in row if c is not None), None)
                if first_val:
                    first_str = str(first_val).strip().upper()
                    if any(first_str.startswith(p) for p in ['CO_', 'TX_', 'TP_', 'IN_', 'NU_', 'SG_']):
                        break

            # Extrai candidato a código (inteiro) e descrição (texto)
            code = None
            desc = None
            for cell in row:
                if cell is None:
                    continue
                if code is None:
                    try:
                        iv = int(cell)
                        if 1 <= iv <= 99999:
                            code = iv
                            continue
                    except (ValueError, TypeError):
                        pass
                if code is not None and desc is None:
                    if isinstance(cell, str) and cell.strip():
                        desc = cell.strip()
                        break

            if code is not None and desc is not None:
                desc_lower = desc.lower()

                # Verifica se é prova adaptada ou digital (exclusão permanente)
                is_adapted = any(kw in desc_lower for kw in ADAPTED_TEST_KEYWORDS)
                if is_adapted:
                    continue

                # Classifica se é Reaplicação / PPL (P2) ou Regular (P1)
                is_ppl = any(kw in desc_lower for kw in PPL_TEST_KEYWORDS)
                tp_aplicacao = 'P2' if is_ppl else 'P1'

                # Identifica cor padronizada oficial
                standard_color = None
                for col in REGULAR_COLORS:
                    c_low = col.lower()
                    if desc_lower.startswith(c_low) or desc_lower == c_low or f" {c_low}" in desc_lower:
                        standard_color = normalize_color(col)
                        break

                if standard_color is not None:
                    records.append({
                        'SG_AREA': TARGET_AREA,
                        'CO_PROVA': code,
                        'TX_COR': standard_color,
                        'TP_APLICACAO': tp_aplicacao,
                        'DESC_ORIGINAL': desc
                    })

        if records:
            break

    wb.close()

    # Reconciliação com omissões conhecidas do INEP (ex: 2011)
    found_codes = {r['CO_PROVA'] for r in records}
    
    # 1. Checa se o dicionário é de 2011 e 136 não está presente
    if '2011' in dictionary_path.name and 136 not in found_codes:
        records.append(KNOWN_DICTIONARY_OMISSIONS[136])
        found_codes.add(136)

    # 2. Se um CSV de itens foi passado, verifica se há códigos conhecidos adicionais
    if csv_path and csv_path.exists():
        try:
            df_csv = pd.read_csv(csv_path, sep=';', encoding='latin1', nrows=5000)
            if 'SG_AREA' in df_csv.columns and 'CO_PROVA' in df_csv.columns:
                mt_csv_codes = set(df_csv[df_csv['SG_AREA'] == TARGET_AREA]['CO_PROVA'].dropna().astype(int).unique())
                for missing_code in (mt_csv_codes - found_codes):
                    if missing_code in KNOWN_DICTIONARY_OMISSIONS:
                        records.append(KNOWN_DICTIONARY_OMISSIONS[missing_code])
                        found_codes.add(missing_code)
        except Exception:
            pass

    if not records:
        raise RuntimeError(f"Nenhum código de Matemática (CO_PROVA_MT) encontrado em {dictionary_path.name}.")

    return pd.DataFrame(records)

def parse_dictionary(dictionary_path: Path, year: Optional[int] = None) -> pd.DataFrame:
    """
    Função de compatibilidade que invoca a leitura dos códigos de Matemática.
    """
    return parse_math_exam_codes(dictionary_path)
