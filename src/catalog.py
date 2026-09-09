"""
Catálogo estático de arquivos PDF de provas regulares do ENEM (2009 a 2024).

Mapeia deterministicamente (Ano, Dia, Cor_Padronizada) para o nome exato do
arquivo PDF do caderno de prova da Primeira Aplicação Regular (P1).
"""

from typing import Dict, Optional, Tuple

# Normalização de nomes de cores encontradas nas colunas TX_COR dos CSVs
COLOR_NORMALIZATION = {
    'AZUL': 'AZUL',
    'AMARELO': 'AMARELO',
    'AMARELA': 'AMARELO',
    'BRANCO': 'BRANCO',
    'BRANCA': 'BRANCO',
    'ROSA': 'ROSA',
    'CINZA': 'CINZA',
    'VERDE': 'VERDE'
}

# Tabela estática oficial de cadernos regulares (1ª Aplicação Regular)
EXAM_PDF_CATALOG: Dict[int, Dict[Tuple[int, str], str]] = {
    2009: {
        (1, 'AZUL'): 'ENEM_2009_PROVA_DIA_1_AZUL_1.pdf',
        (1, 'AMARELO'): 'ENEM_2009_PROVA_DIA_1_AMARELO_2.pdf',
        (1, 'BRANCO'): 'ENEM_2009_PROVA_DIA_1_BRANCO_3.pdf',
        (1, 'ROSA'): 'ENEM_2009_PROVA_DIA_1_ROSA_4.pdf',
        (2, 'AMARELO'): 'ENEM_2009_PROVA_DIA_2_AMARELO_5.pdf',
        (2, 'CINZA'): 'ENEM_2009_PROVA_DIA_2_CINZA_6.pdf',
        (2, 'AZUL'): 'ENEM_2009_PROVA_DIA_2_AZUL_7.pdf',
        (2, 'ROSA'): 'ENEM_2009_PROVA_DIA_2_ROSA_8.pdf',
    },
    2010: {
        (1, 'AZUL'): 'ENEM_2010_PROVA_GAB_DIA_1_AZUL_1.pdf',
        (2, 'AZUL'): 'ENEM_2010_PROVA_GAB_DIA_2_AZUL_7.pdf',
    },
    2011: {
        (1, 'BRANCO'): 'ENEM_2011_P1_CAD_03_DIA_1_BRANCO_LEDOR.pdf',
        (2, 'CINZA'): 'ENEM_2011_P1_CAD_06_DIA_2_CINZA_LEDOR.pdf',
    },
    2012: {
        (1, 'AMARELO'): 'caderno_enem2012_sab_amarelo.pdf',
        (1, 'AZUL'): 'caderno_enem2012_sab_azul.pdf',
        (1, 'BRANCO'): 'caderno_enem2012_sab_branco.pdf',
        (1, 'ROSA'): 'caderno_enem2012_sab_rosa.pdf',
        (2, 'AMARELO'): 'caderno_enem2012_dom_amarelo.pdf',
        (2, 'AZUL'): 'caderno_enem2012_dom_azul.pdf',
        (2, 'CINZA'): 'caderno_enem2012_dom_cinza.pdf',
        (2, 'ROSA'): 'caderno_enem2012_dom_rosa.pdf',
    },
    2013: {
        (1, 'AZUL'): 'Caderno1_Azul_Sab.pdf',
        (1, 'AMARELO'): 'Caderno2_Amarelo_Sab.pdf',
        (1, 'BRANCO'): 'Caderno3_Branco_Sab.pdf',
        (1, 'ROSA'): 'Caderno4_Rosa_Sab.pdf',
        (2, 'AMARELO'): 'Caderno5_Amarelo_Dom.pdf',
        (2, 'CINZA'): 'Caderno6_Cinza_Dom.pdf',
        (2, 'AZUL'): 'Caderno7_Azul_Dom.pdf',
        (2, 'ROSA'): 'Caderno8_Rosa_Dom.pdf',
    },
    2014: {
        (1, 'AZUL'): 'Caderno1_Azul_Sab.pdf',
        (1, 'AMARELO'): 'Caderno2_Amarelo_Sab.pdf',
        (1, 'BRANCO'): 'Caderno3_Branco_Sab.pdf',
        (1, 'ROSA'): 'Caderno4_Rosa_Sab.pdf',
        (2, 'AMARELO'): 'Caderno5_Amarelo_Dom.pdf',
        (2, 'CINZA'): 'Caderno6_Cinza_Dom.pdf',
        (2, 'AZUL'): 'Caderno7_Azul_Dom.pdf',
        (2, 'ROSA'): 'Caderno8_Rosa_Dom.pdf',
    },
    2015: {
        (1, 'AZUL'): 'Caderno1_Azul_Sab.pdf',
        (1, 'AMARELO'): 'Caderno2_Amarelo_Sab.pdf',
        (1, 'BRANCO'): 'Caderno3_Branco_Sab.pdf',
        (1, 'ROSA'): 'Caderno4_Rosa_Sab.pdf',
        (2, 'AMARELO'): 'Caderno5_Amarelo_Dom.pdf',
        (2, 'CINZA'): 'Caderno6_Cinza_Dom.pdf',
        (2, 'AZUL'): 'Caderno7_Azul_Dom.pdf',
        (2, 'ROSA'): 'Caderno8_Rosa_Dom.pdf',
    },
    2016: {
        (1, 'AZUL'): 'CAD_ENEM_2016_DIA_1_01_AZUL.pdf',
        (1, 'AMARELO'): 'CAD_ENEM_2016_DIA_1_02_AMARELO.pdf',
        (1, 'BRANCO'): 'CAD_ENEM_2016_DIA_1_03_BRANCO.pdf',
        (1, 'ROSA'): 'CAD_ENEM_2016_DIA_1_04_ROSA.pdf',
        (2, 'AMARELO'): 'CAD_ENEM_2016_DIA_2_05_AMARELO.pdf',
        (2, 'CINZA'): 'CAD_ENEM_2016_DIA_2_06_CINZA.pdf',
        (2, 'AZUL'): 'CAD_ENEM_2016_DIA_2_07_AZUL.pdf',
        (2, 'ROSA'): 'CAD_ENEM_2016_DIA_2_08_ROSA.pdf',
    },
    2017: {
        (1, 'AZUL'): 'ENEM_2017_P1_CAD_01_DIA_1_AZUL.pdf',
        (1, 'AMARELO'): 'ENEM_2017_P1_CAD_02_DIA_1_AMARELO.pdf',
        (1, 'BRANCO'): 'ENEM_2017_P1_CAD_03_DIA_1_BRANCO.pdf',
        (1, 'ROSA'): 'ENEM_2017_P1_CAD_04_DIA_1_ROSA.pdf',
        (2, 'AMARELO'): 'ENEM_2017_P1_CAD_05_DIA_2_AMARELO.pdf',
        (2, 'CINZA'): 'ENEM_2017_P1_CAD_06_DIA_2_CINZA.pdf',
        (2, 'AZUL'): 'ENEM_2017_P1_CAD_07_DIA_2_AZUL.pdf',
        (2, 'ROSA'): 'ENEM_2017_P1_CAD_08_DIA_2_ROSA.pdf',
    },
    2018: {
        (1, 'AZUL'): 'ENEM_2018_P1_CAD_01_DIA_1_AZUL.pdf',
        (1, 'AMARELO'): 'ENEM_2018_P1_CAD_02_DIA_1_AMARELO.pdf',
        (1, 'BRANCO'): 'ENEM_2018_P1_CAD_03_DIA_1_BRANCO.pdf',
        (1, 'ROSA'): 'ENEM_2018_P1_CAD_04_DIA_1_ROSA.pdf',
        (2, 'AMARELO'): 'ENEM_2018_P1_CAD_05_DIA_2_AMARELO.pdf',
        (2, 'CINZA'): 'ENEM_2018_P1_CAD_06_DIA_2_CINZA.pdf',
        (2, 'AZUL'): 'ENEM_2018_P1_CAD_07_DIA_2_AZUL.pdf',
        (2, 'ROSA'): 'ENEM_2018_P1_CAD_08_DIA_2_ROSA.pdf',
    },
    2019: {
        (1, 'AZUL'): 'ENEM_2019_P1_CAD_01_DIA_1_AZUL.pdf',
        (1, 'AMARELO'): 'ENEM_2019_P1_CAD_02_DIA_1_AMARELO.pdf',
        (1, 'BRANCO'): 'ENEM_2019_P1_CAD_03_DIA_1_BRANCO.pdf',
        (1, 'ROSA'): 'ENEM_2019_P1_CAD_04_DIA_1_ROSA.pdf',
        (2, 'AMARELO'): 'ENEM_2019_P1_CAD_05_DIA_2_AMARELO.pdf',
        (2, 'CINZA'): 'ENEM_2019_P1_CAD_06_DIA_2_CINZA.pdf',
        (2, 'AZUL'): 'ENEM_2019_P1_CAD_07_DIA_2_AZUL.pdf',
        (2, 'ROSA'): 'ENEM_2019_P1_CAD_08_DIA_2_ROSA.pdf',
    },
    2020: {
        (1, 'AZUL'): 'ENEM_2020_P1_CAD_01_DIA_1_AZUL.pdf',
        (1, 'AMARELO'): 'ENEM_2020_P1_CAD_02_DIA_1_AMARELO.pdf',
        (1, 'BRANCO'): 'ENEM_2020_P1_CAD_03_DIA_1_BRANCO.pdf',
        (1, 'ROSA'): 'ENEM_2020_P1_CAD_04_DIA_1_ROSA.pdf',
        (2, 'AMARELO'): 'ENEM_2020_P1_CAD_05_DIA_2_AMARELO.pdf',
        (2, 'CINZA'): 'ENEM_2020_P1_CAD_06_DIA_2_CINZA.pdf',
        (2, 'AZUL'): 'ENEM_2020_P1_CAD_07_DIA_2_AZUL.pdf',
        (2, 'ROSA'): 'ENEM_2020_P1_CAD_08_DIA_2_ROSA.pdf',
    },
    2021: {
        (1, 'AZUL'): 'ENEM_2021_P1_CAD_01_DIA_1_AZUL.pdf',
        (1, 'AMARELO'): 'ENEM_2021_P1_CAD_02_DIA_1_AMARELO.pdf',
        (1, 'BRANCO'): 'ENEM_2021_P1_CAD_03_DIA_1_BRANCO.pdf',
        (1, 'ROSA'): 'ENEM_2021_P1_CAD_04_DIA_1_ROSA.pdf',
        (2, 'AMARELO'): 'ENEM_2021_P1_CAD_05_DIA_2_AMARELO.pdf',
        (2, 'CINZA'): 'ENEM_2021_P1_CAD_06_DIA_2_CINZA.pdf',
        (2, 'AZUL'): 'ENEM_2021_P1_CAD_07_DIA_2_AZUL.pdf',
        (2, 'ROSA'): 'ENEM_2021_P1_CAD_08_DIA_2_ROSA.pdf',
    },
    2022: {
        (1, 'AZUL'): 'ENEM_2022_P1_CAD_01_DIA_1_AZUL.pdf',
        (1, 'AMARELO'): 'ENEM_2022_P1_CAD_02_DIA_1_AMARELO.pdf',
        (1, 'BRANCO'): 'ENEM_2022_P1_CAD_03_DIA_1_BRANCO.pdf',
        (1, 'ROSA'): 'ENEM_2022_P1_CAD_04_DIA_1_ROSA.pdf',
        (2, 'AMARELO'): 'ENEM_2022_P1_CAD_05_DIA_2_AMARELO.pdf',
        (2, 'CINZA'): 'ENEM_2022_P1_CAD_06_DIA_2_CINZA.pdf',
        (2, 'AZUL'): 'ENEM_2022_P1_CAD_07_DIA_2_AZUL.pdf',
        (2, 'ROSA'): 'ENEM_2022_P1_CAD_08_DIA_2_ROSA.pdf',
    },
    2023: {
        (1, 'AZUL'): 'ENEM_2023_P1_CAD_01_DIA_1_AZUL.pdf',
        (1, 'AMARELO'): 'ENEM_2023_P1_CAD_02_DIA_1_AMARELO.pdf',
        (1, 'BRANCO'): 'ENEM_2023_P1_CAD_03_DIA_1_BRANCO.pdf',
        (2, 'AMARELO'): 'ENEM_2023_P1_CAD_05_DIA_2_AMARELO.pdf',
        (2, 'CINZA'): 'ENEM_2023_P1_CAD_06_DIA_2_CINZA.pdf',
        (2, 'AZUL'): 'ENEM_2023_P1_CAD_07_DIA_2_AZUL.pdf',
        (2, 'ROSA'): 'ENEM_2023_P1_CAD_08_DIA_2_ROSA.pdf',
    },
    2024: {
        (1, 'AZUL'): 'ENEM_2024_P1_CAD_01_DIA_1_AZUL.pdf',
        (1, 'AMARELO'): 'ENEM_2024_P1_CAD_02_DIA_1_AMARELO.pdf',
        (1, 'BRANCO'): 'ENEM_2024_P1_CAD_03_DIA_1_BRANCO.pdf',
        (1, 'VERDE'): 'ENEM_2024_P1_CAD_04_DIA_1_VERDE.pdf',
        (2, 'AMARELO'): 'ENEM_2024_P1_CAD_05_DIA_2_AMARELO.pdf',
        (2, 'CINZA'): 'ENEM_2024_P1_CAD_06_DIA_2_CINZA.pdf',
        (2, 'AZUL'): 'ENEM_2024_P1_CAD_07_DIA_2_AZUL.pdf',
        (2, 'VERDE'): 'ENEM_2024_P1_CAD_08_DIA_2_VERDE.pdf',
    },
}

def normalize_color(color_raw: str) -> Optional[str]:
    """
    Padroniza a cor informada no CSV para a chave unificada do catálogo.
    """
    if not color_raw:
        return None
    cleaned = str(color_raw).strip().upper()
    return COLOR_NORMALIZATION.get(cleaned)

def get_pdf_filename(year: int, day: int, color_raw: str) -> Optional[str]:
    """
    Retorna o nome do PDF correspondente a um ano, dia e cor de prova regular.
    """
    norm_color = normalize_color(color_raw)
    if not norm_color:
        return None

    year_catalog = EXAM_PDF_CATALOG.get(year)
    if not year_catalog:
        return None

    return year_catalog.get((day, norm_color))
