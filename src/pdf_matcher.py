"""
Módulo para localização e mapeamento dinâmico dos arquivos PDF de prova.
"""

from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from src.config import AREA_TO_DAY, EXCLUDED_TEST_KEYWORDS

def match_pdf_for_exam(provas_dir: Path, area: str, color: str) -> Optional[Path]:
    """
    Encontra o arquivo PDF de caderno de questões correspondente a uma área e cor regulares.
    """
    day = AREA_TO_DAY.get(area)
    if not day:
        raise ValueError(f"Área desconhecida: {area}")

    color_root = color.lower()[:4]  # azul, amar, verd, cinz, bran
    candidates = []

    for file_path in provas_dir.glob("*.pdf"):
        fname = file_path.name.lower()

        # Deve ser caderno de questões (CAD) e não gabarito (GAB)
        if "cad" not in fname or "gab" in fname:
            continue

        # Primeira aplicação regular (P1)
        if "p1" not in fname:
            continue

        # Excluir provas adaptadas e especiais
        if any(kw in fname for kw in EXCLUDED_TEST_KEYWORDS):
            continue

        # Deve corresponder ao dia e cor
        day_pattern = f"dia_{day}"
        if day_pattern in fname and color_root in fname:
            candidates.append(file_path)

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        # Se houver múltiplos, prefere o que não tem modificadores adicionais
        exact = [c for c in candidates if not any(w in c.name.lower() for w in ['ampliada', 'ledor', 'libras'])]
        if len(exact) == 1:
            return exact[0]
        return candidates[0]

    return None

def build_exam_pdf_mapping(provas_dir: Path, df_dict: pd.DataFrame) -> Dict[int, Path]:
    """
    Constrói o dicionário mapeando CO_PROVA -> Caminho do PDF do caderno.
    """
    if not provas_dir.exists():
        raise FileNotFoundError(f"Diretório de provas não encontrado em: {provas_dir}")

    mapping: Dict[int, Path] = {}
    for _, row in df_dict.iterrows():
        co_prova = int(row['CO_PROVA'])
        area = row['SG_AREA']
        color = row['TX_COR']

        pdf_path = match_pdf_for_exam(provas_dir, area, color)
        if not pdf_path:
            raise RuntimeError(f"Não foi possível localizar o PDF para CO_PROVA={co_prova}, Área={area}, Cor={color}")

        mapping[co_prova] = pdf_path

    return mapping
