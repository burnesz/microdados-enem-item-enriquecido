"""
Catálogo estático oficial de arquivos PDF de provas do ENEM (2009 a 2024).

Mapeia deterministicamente (Ano, Aplicação, Dia, Cor_Padronizada) para o nome exato do
arquivo PDF do caderno de prova para Primeira Aplicação (P1) e Reaplicação / PPL (P2).
"""

from typing import Dict, Optional, Tuple, Union

# Normalização de nomes de cores encontradas nas colunas TX_COR dos CSVs e Dicionários
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

# Tabela estática consolidada cobrindo Primeira Aplicação (P1) e Reaplicação/PPL (P2)
# Chaves suportadas por ano:
# - ('P1', dia, cor) e ('P2', dia, cor)
# - (dia, cor) mantido como atalho compatível para P1
EXAM_PDF_CATALOG: Dict[int, Dict[Union[Tuple[str, int, str], Tuple[int, str]], str]] = {
    2009: {
        ('P1', 1, 'AZUL'): 'ENEM_2009_PROVA_DIA_1_AZUL_1.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2009_PROVA_DIA_1_AMARELO_2.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2009_PROVA_DIA_1_BRANCO_3.pdf',
        ('P1', 1, 'ROSA'): 'ENEM_2009_PROVA_DIA_1_ROSA_4.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2009_PROVA_DIA_2_AMARELO_5.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2009_PROVA_DIA_2_CINZA_6.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2009_PROVA_DIA_2_AZUL_7.pdf',
        ('P1', 2, 'ROSA'): 'ENEM_2009_PROVA_DIA_2_ROSA_8.pdf',
    },
    2010: {
        ('P1', 1, 'AZUL'): 'ENEM_2010_PROVA_GAB_DIA_1_AZUL_1.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2010_PROVA_GAB_DIA_2_AZUL_7.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2010_PROVA_GAB_DIA_2_AZUL_7(2_Aplicação).pdf',
    },
    2011: {
        ('P1', 1, 'BRANCO'): 'ENEM_2011_P1_CAD_03_DIA_1_BRANCO_LEDOR.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2011_P1_CAD_06_DIA_2_CINZA_LEDOR.pdf',
        ('P2', 2, 'CINZA'): 'ENEM_2011_P2_CAD_06_DIA_2_CINZA.pdf',
    },
    2012: {
        ('P1', 1, 'AMARELO'): 'caderno_enem2012_sab_amarelo.pdf',
        ('P1', 1, 'AZUL'): 'caderno_enem2012_sab_azul.pdf',
        ('P1', 1, 'BRANCO'): 'caderno_enem2012_sab_branco.pdf',
        ('P1', 1, 'ROSA'): 'caderno_enem2012_sab_rosa.pdf',
        ('P1', 2, 'AMARELO'): 'caderno_enem2012_dom_amarelo.pdf',
        ('P1', 2, 'AZUL'): 'caderno_enem2012_dom_azul.pdf',
        ('P1', 2, 'CINZA'): 'caderno_enem2012_dom_cinza.pdf',
        ('P1', 2, 'ROSA'): 'caderno_enem2012_dom_rosa.pdf',
        ('P2', 2, 'CINZA'): 'caderno_enem2012_dom_cinza_p2.pdf',
    },
    2013: {
        ('P1', 1, 'AZUL'): 'Caderno1_Azul_Sab.pdf',
        ('P1', 1, 'AMARELO'): 'Caderno2_Amarelo_Sab.pdf',
        ('P1', 1, 'BRANCO'): 'Caderno3_Branco_Sab.pdf',
        ('P1', 1, 'ROSA'): 'Caderno4_Rosa_Sab.pdf',
        ('P1', 2, 'AMARELO'): 'Caderno5_Amarelo_Dom.pdf',
        ('P1', 2, 'CINZA'): 'Caderno6_Cinza_Dom.pdf',
        ('P1', 2, 'AZUL'): 'Caderno7_Azul_Dom.pdf',
        ('P1', 2, 'ROSA'): 'Caderno8_Rosa_Dom.pdf',
        ('P2', 2, 'CINZA'): 'Caderno6_Cinza_Dom_p2.pdf',
    },
    2014: {
        ('P1', 1, 'AZUL'): 'Caderno1_Azul_Sab.pdf',
        ('P1', 1, 'AMARELO'): 'Caderno2_Amarelo_Sab.pdf',
        ('P1', 1, 'BRANCO'): 'Caderno3_Branco_Sab.pdf',
        ('P1', 1, 'ROSA'): 'Caderno4_Rosa_Sab.pdf',
        ('P1', 2, 'AMARELO'): 'Caderno5_Amarelo_Dom.pdf',
        ('P1', 2, 'CINZA'): 'Caderno6_Cinza_Dom.pdf',
        ('P1', 2, 'AZUL'): 'Caderno7_Azul_Dom.pdf',
        ('P1', 2, 'ROSA'): 'Caderno8_Rosa_Dom.pdf',
        ('P2', 2, 'CINZA'): 'Caderno6_Cinza_Dom_p2.pdf',
    },
    2015: {
        ('P1', 1, 'AZUL'): 'Caderno1_Azul_Sab.pdf',
        ('P1', 1, 'AMARELO'): 'Caderno2_Amarelo_Sab.pdf',
        ('P1', 1, 'BRANCO'): 'Caderno3_Branco_Sab.pdf',
        ('P1', 1, 'ROSA'): 'Caderno4_Rosa_Sab.pdf',
        ('P1', 2, 'AMARELO'): 'Caderno5_Amarelo_Dom.pdf',
        ('P1', 2, 'CINZA'): 'Caderno6_Cinza_Dom.pdf',
        ('P1', 2, 'AZUL'): 'Caderno7_Azul_Dom.pdf',
        ('P1', 2, 'ROSA'): 'Caderno8_Rosa_Dom.pdf',
        ('P2', 2, 'AMARELO'): 'Caderno5_Amarelo_Dom_2.pdf.pdf',
        ('P2', 2, 'CINZA'): 'Caderno6_Cinza_Dom_2.pdf.pdf',
        ('P2', 2, 'AZUL'): 'Caderno7_Azul_Dom_2.pdf.pdf',
        ('P2', 2, 'ROSA'): 'Caderno8_Rosa_Dom_2.pdf.pdf',
    },
    2016: {
        ('P1', 1, 'AZUL'): 'CAD_ENEM_2016_DIA_1_01_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'CAD_ENEM_2016_DIA_1_02_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'CAD_ENEM_2016_DIA_1_03_BRANCO.pdf',
        ('P1', 1, 'ROSA'): 'CAD_ENEM_2016_DIA_1_04_ROSA.pdf',
        ('P1', 2, 'AMARELO'): 'CAD_ENEM_2016_DIA_2_05_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'CAD_ENEM_2016_DIA_2_06_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'CAD_ENEM_2016_DIA_2_07_AZUL.pdf',
        ('P1', 2, 'ROSA'): 'CAD_ENEM_2016_DIA_2_08_ROSA.pdf',
        ('P2', 2, 'AMARELO'): 'CAD_ENEM_2016_DIA_2_05_AMARELO_2.pdf',
        ('P2', 2, 'CINZA'): 'CAD_ENEM_2016_DIA_2_06_CINZA_2.pdf',
        ('P2', 2, 'AZUL'): 'CAD_ENEM_2016_DIA_2_07_AZUL_2.pdf',
        ('P2', 2, 'ROSA'): 'CAD_ENEM_2016_DIA_2_08_ROSA_2.pdf',
    },
    2017: {
        ('P1', 1, 'AZUL'): 'ENEM_2017_P1_CAD_01_DIA_1_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2017_P1_CAD_02_DIA_1_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2017_P1_CAD_03_DIA_1_BRANCO.pdf',
        ('P1', 1, 'ROSA'): 'ENEM_2017_P1_CAD_04_DIA_1_ROSA.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2017_P1_CAD_05_DIA_2_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2017_P1_CAD_06_DIA_2_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2017_P1_CAD_07_DIA_2_AZUL.pdf',
        ('P1', 2, 'ROSA'): 'ENEM_2017_P1_CAD_08_DIA_2_ROSA.pdf',
        ('P2', 2, 'AMARELO'): 'ENEM_2017_P2_CAD_05_DIA_2_AMARELO.pdf',
        ('P2', 2, 'CINZA'): 'ENEM_2017_P2_CAD_06_DIA_2_CINZA.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2017_P2_CAD_07_DIA_2_AZUL.pdf',
        ('P2', 2, 'ROSA'): 'ENEM_2017_P2_CAD_08_DIA_2_ROSA.pdf',
    },
    2018: {
        ('P1', 1, 'AZUL'): 'ENEM_2018_P1_CAD_01_DIA_1_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2018_P1_CAD_02_DIA_1_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2018_P1_CAD_03_DIA_1_BRANCO.pdf',
        ('P1', 1, 'ROSA'): 'ENEM_2018_P1_CAD_04_DIA_1_ROSA.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2018_P1_CAD_05_DIA_2_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2018_P1_CAD_06_DIA_2_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2018_P1_CAD_07_DIA_2_AZUL.pdf',
        ('P1', 2, 'ROSA'): 'ENEM_2018_P1_CAD_08_DIA_2_ROSA.pdf',
        ('P2', 2, 'AMARELO'): 'ENEM_2018_P2_CAD_05_DIA_2_AMARELO.pdf',
        ('P2', 2, 'CINZA'): 'ENEM_2018_P2_CAD_06_DIA_2_CINZA.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2018_P2_CAD_07_DIA_2_AZUL.pdf',
        ('P2', 2, 'ROSA'): 'ENEM_2018_P2_CAD_08_DIA_2_ROSA.pdf',
    },
    2019: {
        ('P1', 1, 'AZUL'): 'ENEM_2019_P1_CAD_01_DIA_1_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2019_P1_CAD_02_DIA_1_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2019_P1_CAD_03_DIA_1_BRANCO.pdf',
        ('P1', 1, 'ROSA'): 'ENEM_2019_P1_CAD_04_DIA_1_ROSA.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2019_P1_CAD_05_DIA_2_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2019_P1_CAD_06_DIA_2_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2019_P1_CAD_07_DIA_2_AZUL.pdf',
        ('P1', 2, 'ROSA'): 'ENEM_2019_P1_CAD_08_DIA_2_ROSA.pdf',
        ('P2', 2, 'AMARELO'): 'ENEM_2019_P2_CAD_05_DIA_2_AMARELO.pdf',
        ('P2', 2, 'CINZA'): 'ENEM_2019_P2_CAD_06_DIA_2_CINZA.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2019_P2_CAD_07_DIA_2_AZUL.pdf',
        ('P2', 2, 'ROSA'): 'ENEM_2019_P2_CAD_08_DIA_2_ROSA.pdf',
    },
    2020: {
        ('P1', 1, 'AZUL'): 'ENEM_2020_P1_CAD_01_DIA_1_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2020_P1_CAD_02_DIA_1_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2020_P1_CAD_03_DIA_1_BRANCO.pdf',
        ('P1', 1, 'ROSA'): 'ENEM_2020_P1_CAD_04_DIA_1_ROSA.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2020_P1_CAD_05_DIA_2_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2020_P1_CAD_06_DIA_2_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2020_P1_CAD_07_DIA_2_AZUL.pdf',
        ('P1', 2, 'ROSA'): 'ENEM_2020_P1_CAD_08_DIA_2_ROSA.pdf',
        ('P2', 2, 'AMARELO'): 'ENEM_2020_P2_CAD_05_DIA_2_AMARELO.pdf',
        ('P2', 2, 'CINZA'): 'ENEM_2020_P2_CAD_06_DIA_2_CINZA.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2020_P2_CAD_07_DIA_2_AZUL.pdf',
        ('P2', 2, 'ROSA'): 'ENEM_2020_P2_CAD_08_DIA_2_ROSA.pdf',
    },
    2021: {
        ('P1', 1, 'AZUL'): 'ENEM_2021_P1_CAD_01_DIA_1_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2021_P1_CAD_02_DIA_1_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2021_P1_CAD_03_DIA_1_BRANCO.pdf',
        ('P1', 1, 'ROSA'): 'ENEM_2021_P1_CAD_04_DIA_1_ROSA.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2021_P1_CAD_05_DIA_2_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2021_P1_CAD_06_DIA_2_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2021_P1_CAD_07_DIA_2_AZUL.pdf',
        ('P1', 2, 'ROSA'): 'ENEM_2021_P1_CAD_08_DIA_2_ROSA.pdf',
        ('P2', 2, 'AMARELO'): 'ENEM_2021_P2_CAD_05_DIA_2_AMARELO.pdf',
        ('P2', 2, 'CINZA'): 'ENEM_2021_P2_CAD_06_DIA_2_CINZA.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2021_P2_CAD_07_DIA_2_AZUL.pdf',
        ('P2', 2, 'ROSA'): 'ENEM_2021_P2_CAD_08_DIA_2_ROSA.pdf',
    },
    2022: {
        ('P1', 1, 'AZUL'): 'ENEM_2022_P1_CAD_01_DIA_1_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2022_P1_CAD_02_DIA_1_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2022_P1_CAD_03_DIA_1_BRANCO.pdf',
        ('P1', 1, 'ROSA'): 'ENEM_2022_P1_CAD_04_DIA_1_ROSA.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2022_P1_CAD_05_DIA_2_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2022_P1_CAD_06_DIA_2_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2022_P1_CAD_07_DIA_2_AZUL.pdf',
        ('P1', 2, 'ROSA'): 'ENEM_2022_P1_CAD_08_DIA_2_ROSA.pdf',
        ('P2', 2, 'AMARELO'): 'ENEM_2022_P2_CAD_05_DIA_2_AMARELO.pdf',
        ('P2', 2, 'CINZA'): 'ENEM_2022_P2_CAD_06_DIA_2_CINZA.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2022_P2_CAD_07_DIA_2_AZUL.pdf',
        ('P2', 2, 'ROSA'): 'ENEM_2022_P2_CAD_08_DIA_2_ROSA.pdf',
    },
    2023: {
        ('P1', 1, 'AZUL'): 'ENEM_2023_P1_CAD_01_DIA_1_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2023_P1_CAD_02_DIA_1_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2023_P1_CAD_03_DIA_1_BRANCO.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2023_P1_CAD_05_DIA_2_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2023_P1_CAD_06_DIA_2_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2023_P1_CAD_07_DIA_2_AZUL.pdf',
        ('P1', 2, 'ROSA'): 'ENEM_2023_P1_CAD_08_DIA_2_ROSA.pdf',
        ('P2', 2, 'AMARELO'): 'ENEM_2023_P2_CAD_05_DIA_2_AMARELO.pdf',
        ('P2', 2, 'CINZA'): 'ENEM_2023_P2_CAD_06_DIA_2_CINZA.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2023_P2_CAD_07_DIA_2_AZUL.pdf',
        ('P2', 2, 'ROSA'): 'ENEM_2023_P2_CAD_08_DIA_2_ROSA.pdf',
    },
    2024: {
        ('P1', 1, 'AZUL'): 'ENEM_2024_P1_CAD_01_DIA_1_AZUL.pdf',
        ('P1', 1, 'AMARELO'): 'ENEM_2024_P1_CAD_02_DIA_1_AMARELO.pdf',
        ('P1', 1, 'BRANCO'): 'ENEM_2024_P1_CAD_03_DIA_1_BRANCO.pdf',
        ('P1', 1, 'VERDE'): 'ENEM_2024_P1_CAD_04_DIA_1_VERDE.pdf',
        ('P1', 2, 'AMARELO'): 'ENEM_2024_P1_CAD_05_DIA_2_AMARELO.pdf',
        ('P1', 2, 'CINZA'): 'ENEM_2024_P1_CAD_06_DIA_2_CINZA.pdf',
        ('P1', 2, 'AZUL'): 'ENEM_2024_P1_CAD_07_DIA_2_AZUL.pdf',
        ('P1', 2, 'VERDE'): 'ENEM_2024_P1_CAD_08_DIA_2_VERDE.pdf',
        ('P2', 2, 'AZUL'): 'ENEM_2024_P2_CAD_07_DIA_2_AZUL.pdf',
    },
}

# Adiciona atalhos de tupla de 2 elementos (dia, cor) para P1 garantindo retrocompatibilidade
for _year_cat in EXAM_PDF_CATALOG.values():
    _shortcuts = {}
    for _key, _val in _year_cat.items():
        if isinstance(_key, tuple) and len(_key) == 3 and _key[0] == 'P1':
            _shortcuts[(_key[1], _key[2])] = _val
    _year_cat.update(_shortcuts)


def normalize_color(color_raw: str) -> Optional[str]:
    """
    Padroniza a cor informada no CSV ou Dicionário para a chave unificada do catálogo.
    """
    if not color_raw:
        return None
    cleaned = str(color_raw).strip().upper()
    return COLOR_NORMALIZATION.get(cleaned)


def get_pdf_filename(
    year: int,
    day: int,
    color_raw: str,
    application: str = 'P1'
) -> Optional[str]:
    """
    Retorna o nome do arquivo PDF para determinado ano, dia, cor e aplicação (P1 ou P2).
    """
    norm_color = normalize_color(color_raw)
    if not norm_color:
        return None

    year_catalog = EXAM_PDF_CATALOG.get(year)
    if not year_catalog:
        return None

    app_upper = str(application).strip().upper()
    if app_upper in ('P1', 'REGULAR', 'PRIMEIRA', '1'):
        app_key = 'P1'
    elif app_upper in ('P2', 'PPL', 'REAPLICACAO', 'REAPLICAÇÃO', 'SEGUNDA', '2'):
        app_key = 'P2'
    else:
        app_key = 'P1'

    # Busca pela chave ternária ('P1'/'P2', dia, cor)
    filename = year_catalog.get((app_key, day, norm_color))
    if not filename and app_key == 'P1':
        # Fallback para tupla binária
        filename = year_catalog.get((day, norm_color))

    return filename
