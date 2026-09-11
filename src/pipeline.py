"""
Orquestrador principal da pipeline de extração e enriquecimento dos itens do ENEM.
Focado exclusivamente na área de Matemática (MT) com resolução dinâmica pelo Dicionário
e seleção unária determinística de cadernos (1 cor da Prova Regular + 1 cor de Reaplicação/PPL).
"""

from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import time
import pandas as pd

from src.config import (
    TARGET_AREA,
    SUPPORTED_YEARS,
    CONSOLIDATED_OUTPUT_FILENAME,
    CANONICAL_COLUMNS,
    INTEGER_COLUMNS,
    FLOAT_COLUMNS
)
from src.dictionary_parser import parse_math_exam_codes
from src.pdf_matcher import build_selected_math_exams
from src.pdf_extractor import extract_questions_from_pdf

def enforce_column_types(df: pd.DataFrame) -> pd.DataFrame:
    """
    Garante a preservação estrita dos tipos de dados de cada coluna:
    - Colunas inteiras (mesmo com valores ausentes/nulos) são convertidas para Int64
      (evitando que inteiros virem decimais .0 na exportação em CSV).
    - Colunas de parâmetros da TRI são convertidas para float64.
    """
    df = df.copy()
    for col in INTEGER_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('Int64')
    for col in FLOAT_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype('float64')
    return df

def locate_year_paths(root_dir: Path, year: int) -> Tuple[Path, Path, Path]:
    """
    Localiza o arquivo CSV de itens, a pasta de provas em PDF e a planilha do dicionário (.xlsx)
    para o ano informado, suportando pastas aninhadas e variações de maiúsculas/minúsculas.
    """
    year_dir = root_dir / "raw" / f"microdados_enem_{year}"
    if not year_dir.exists():
        raise FileNotFoundError(f"Diretório do ano {year} não encontrado em: {year_dir}")

    nested = year_dir / f"microdados_enem_{year}"
    search_dir = nested if nested.is_dir() else year_dir

    # 1. Localização do CSV de Itens
    csv_path = None
    candidate_dirs = [search_dir / "DADOS", search_dir]
    for d in candidate_dirs:
        if d.is_dir():
            for p in d.iterdir():
                if p.is_file() and p.suffix.lower() == ".csv" and "ITENS" in p.name.upper():
                    csv_path = p
                    break
        if csv_path:
            break

    if not csv_path:
        for p in search_dir.glob("*/*.csv"):
            if "ITENS" in p.name.upper():
                csv_path = p
                break

    if not csv_path:
        raise FileNotFoundError(f"Arquivo CSV de itens de prova não encontrado em {search_dir}")

    # 2. Localização do Dicionário (.xlsx)
    dict_path = None
    dict_candidate_dirs = [
        search_dir / "DICIONÁRIO",
        search_dir / "DICIONARIO",
        search_dir / "Dicionário",
        search_dir / "ANEXOS",
        search_dir
    ]
    for d in dict_candidate_dirs:
        if d.is_dir():
            for p in d.iterdir():
                if p.is_file() and p.suffix.lower() == ".xlsx" and not p.name.startswith("~$"):
                    dict_path = p
                    break
        if dict_path:
            break

    if not dict_path:
        for p in search_dir.glob("*/*.xlsx"):
            if not p.name.startswith("~$"):
                dict_path = p
                break

    if not dict_path:
        raise FileNotFoundError(f"Arquivo de Dicionário (.xlsx) não encontrado em {search_dir}")

    # 3. Localização do diretório de Provas
    provas_dir = None
    for p in search_dir.iterdir():
        if p.is_dir() and "PROVAS" in p.name.upper():
            provas_dir = p
            break

    if not provas_dir:
        for p in search_dir.glob("*/PROVAS*"):
            if p.is_dir():
                provas_dir = p
                break

    if not provas_dir:
        raise FileNotFoundError(f"Diretório de cadernos de prova (PROVAS E GABARITOS) não encontrado em {search_dir}")

    return csv_path, provas_dir, dict_path

def run_enem_pipeline(
    year: int = 2024,
    base_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Executa a pipeline de Matemática para o ano especificado:
    1. Localiza CSV de itens, pasta de provas e Dicionário de Dados (.xlsx).
    2. Lê o Dicionário dinamicamente para classificar códigos de Matemática em Regular (P1) e PPL (P2).
    3. Seleciona deterministicamente 1 caderno Regular e 1 caderno PPL (quando houver).
    4. Filtra ITENS_PROVA_{ANO}.csv mantendo apenas os itens dos cadernos selecionados.
    5. Extrai enunciados, alternativas (A-E) e presença de imagem via PyMuPDF.
    6. Exporta a base enriquecida em processed/itens_prova_{ANO}_enriquecido.csv.
    """
    start_time = time.time()
    root_dir = base_dir or Path(__file__).resolve().parent.parent

    print(f"\n========================================================")
    print(f" Iniciando Pipeline ENEM (Matemática - MT) - Ano: {year}")
    print(f" Escopo: 1 Cor Regular (P1) + 1 Cor Reaplicação/PPL (P2)")
    print(f" Diretório base: {root_dir}")
    print(f"========================================================\n")

    csv_path, provas_dir, dict_path = locate_year_paths(root_dir, year)
    print(f"[1/4] Localizados arquivos de entrada:")
    print(f"      - CSV de Itens: {csv_path.name}")
    print(f"      - Dicionário:   {dict_path.name}")
    print(f"      - Pasta Provas: {provas_dir}")

    # 1. Carrega dados estruturados do CSV de itens
    print(f"\n[2/4] Carregando itens e selecionando cadernos via Dicionário...")
    try:
        df_itens_all = pd.read_csv(csv_path, sep=';', encoding='latin1')
    except Exception:
        df_itens_all = pd.read_csv(csv_path, sep=',', encoding='latin1')

    print(f"      Total de linhas no CSV original: {len(df_itens_all)}")

    # Filtra estritamente para Matemática (MT)
    df_itens = df_itens_all[df_itens_all['SG_AREA'] == TARGET_AREA].copy()
    print(f"      Total de linhas de Matemática (SG_AREA == '{TARGET_AREA}'): {len(df_itens)}")
    if df_itens.empty:
        raise ValueError(f"Nenhum item com SG_AREA == '{TARGET_AREA}' encontrado em {csv_path.name}.")

    # 2. Busca dinâmica dos códigos CO_PROVA_MT no Dicionário (com reconciliação via CSV)
    df_dict_math = parse_math_exam_codes(dict_path, csv_path=csv_path)
    print(f"      Códigos identificados no Dicionário ({len(df_dict_math)}):")
    for _, r in df_dict_math.iterrows():
        print(f"       - [{r['TP_APLICACAO']}] Código {r['CO_PROVA']}: {r['TX_COR']} ('{r['DESC_ORIGINAL']}')")

    # 3. Seleção determinística unária de cadernos (1 Regular + 1 PPL)
    selected_exams = build_selected_math_exams(provas_dir, df_dict_math, year)
    if not selected_exams:
        raise RuntimeError(f"Nenhum caderno de Matemática para {year} foi localizado fisicamente em {provas_dir}.")

    exam_pdf_map: Dict[int, Path] = {c: info['pdf_path'] for c, info in selected_exams.items()}
    exam_app_map: Dict[int, str] = {c: info['tp_aplicacao'] for c, info in selected_exams.items()}
    unique_pdfs = sorted(list(set(exam_pdf_map.values())))

    print(f"\n      Cadernos de Matemática selecionados para extração:")
    for co_prova, info in selected_exams.items():
        print(f"       - [{info['tp_aplicacao']}] Código {co_prova} ({info['tx_cor']}): {info['pdf_path'].name}")

    # 4. Extração de conteúdo dos PDFs via PyMuPDF
    print(f"\n[3/4] Extraindo enunciados, alternativas e imagens dos PDFs de Matemática...")
    pdf_cache: Dict[str, Dict[Tuple[int, Optional[float]], Dict[str, Any]]] = {}
    for pdf_path in unique_pdfs:
        print(f"      Processando {pdf_path.name}...")
        extracted = extract_questions_from_pdf(pdf_path)
        pdf_cache[pdf_path.name] = extracted
        print(f"      -> {len(extracted)} questões extraídas.")

    # 5. Enriquecimento dos dados
    print(f"\n[4/4] Enriquecendo e estruturando dados tabulares de Matemática...")
    selected_codes = set(selected_exams.keys())
    df_reg = df_itens[df_itens['CO_PROVA'].isin(selected_codes)].copy()
    print(f"      Total de itens de Matemática a enriquecer: {len(df_reg)}")

    tp_aplicacao_list = []
    ref_pdf_list = []
    enunciado_list = []
    alt_a_list = []
    alt_b_list = []
    alt_c_list = []
    alt_d_list = []
    alt_e_list = []
    tem_imagem_list = []

    matches_count = 0
    has_tp_lingua = ('TP_LINGUA' in df_reg.columns)

    for _, row in df_reg.iterrows():
        c_prova = int(row['CO_PROVA'])
        c_pos = int(row['CO_POSICAO'])

        t_lang_key = None
        if has_tp_lingua:
            t_lang = row['TP_LINGUA']
            t_lang_key = float(t_lang) if pd.notna(t_lang) else None

        tp_aplicacao_list.append(exam_app_map.get(c_prova, 'REGULAR'))

        pdf_path = exam_pdf_map.get(c_prova)
        pdf_name = pdf_path.name if pdf_path else ""
        ref_pdf_list.append(pdf_name)

        q_dict = pdf_cache.get(pdf_name, {})

        # Resolução de posição no PDF (suporta anos como 2017 onde CO_POSICAO é 1..45 mas no caderno é 136..180)
        target_pos = c_pos
        if target_pos <= 45 and not any(k[0] == target_pos for k in q_dict.keys()):
            if any(k[0] == target_pos + 135 for k in q_dict.keys()):
                target_pos = target_pos + 135
            elif any(k[0] == target_pos + 45 for k in q_dict.keys()):
                target_pos = target_pos + 45
            elif any(k[0] == target_pos + 90 for k in q_dict.keys()):
                target_pos = target_pos + 90

        q_info = q_dict.get((target_pos, t_lang_key))

        # Fallbacks de chave
        if not q_info and t_lang_key is not None:
            q_info = q_dict.get((target_pos, None))
        if not q_info and t_lang_key is None:
            q_info = q_dict.get((target_pos, 0.0))

        if q_info:
            matches_count += 1
            enunciado_list.append(q_info['DESC_ENUNCIADO'])
            alt_a_list.append(q_info['DESC_ALTER_A'])
            alt_b_list.append(q_info['DESC_ALTER_B'])
            alt_c_list.append(q_info['DESC_ALTER_C'])
            alt_d_list.append(q_info['DESC_ALTER_D'])
            alt_e_list.append(q_info['DESC_ALTER_E'])
            tem_imagem_list.append(q_info['IN_ITEM_IMAGEM'])
        else:
            enunciado_list.append("")
            alt_a_list.append("")
            alt_b_list.append("")
            alt_c_list.append("")
            alt_d_list.append("")
            alt_e_list.append("")
            tem_imagem_list.append(0)

    df_reg['ANO_APLICACAO'] = int(year)
    df_reg['TP_APLICACAO'] = tp_aplicacao_list
    df_reg['REF_ARQUIVO_PDF'] = ref_pdf_list
    df_reg['DESC_ENUNCIADO'] = enunciado_list
    df_reg['DESC_ALTER_A'] = alt_a_list
    df_reg['DESC_ALTER_B'] = alt_b_list
    df_reg['DESC_ALTER_C'] = alt_c_list
    df_reg['DESC_ALTER_D'] = alt_d_list
    df_reg['DESC_ALTER_E'] = alt_e_list
    df_reg['IN_ITEM_IMAGEM'] = tem_imagem_list

    # Reordena colunas preservando a ordem canônica
    ordered_cols = [c for c in CANONICAL_COLUMNS if c in df_reg.columns] + [
        c for c in df_reg.columns if c not in CANONICAL_COLUMNS
    ]
    df_reg = df_reg[ordered_cols]

    # Aplica a preservação estrita de tipagem (inteiros sem .0 e floats contínuos)
    df_reg = enforce_column_types(df_reg)

    out_folder = output_dir or (root_dir / "processed")
    out_folder.mkdir(parents=True, exist_ok=True)
    out_file = out_folder / f"itens_prova_{year}_enriquecido.csv"

    # Salva em UTF-8 com BOM e delimitador ;
    df_reg.to_csv(out_file, sep=';', index=False, encoding='utf-8-sig')

    elapsed = time.time() - start_time
    reg_count = (df_reg['TP_APLICACAO'] == 'REGULAR').sum()
    ppl_count = (df_reg['TP_APLICACAO'] == 'REAPLICACAO_PPL').sum()

    print(f"\n========================================================")
    print(f" PIPELINE DE MATEMÁTICA CONCLUÍDA COM SUCESSO!")
    print(f" Edição (Ano):                 {year}")
    print(f" Itens Prova Regular (P1):     {reg_count}")
    print(f" Itens Reaplicação/PPL (P2):   {ppl_count}")
    print(f" Total de itens enriquecidos:  {len(df_reg)}")
    print(f" Taxa de correspondência:      {matches_count}/{len(df_reg)} ({matches_count/len(df_reg)*100:.1f}%)")
    print(f" Itens com imagem identificada: {df_reg['IN_ITEM_IMAGEM'].sum()} ({df_reg['IN_ITEM_IMAGEM'].mean()*100:.1f}%)")
    print(f" Arquivo gerado:               {out_file}")
    print(f" Tempo total:                  {elapsed:.2f}s")
    print(f"========================================================\n")

    return df_reg


def consolidate_all_years(
    output_dir: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    years: Optional[list[int]] = None,
    consolidated_filename: Optional[str] = None
) -> pd.DataFrame:
    """
    Consolida as bases enriquecidas individuais de todas as edições em um único arquivo .csv,
    assegurando a coluna ANO_APLICACAO e a padronização do esquema de colunas.

    :param output_dir: Diretório onde os arquivos enriquecidos residem e onde o consolidado será salvo.
    :param base_dir: Diretório raiz do projeto.
    :param years: Lista de anos a consolidar (padrão: 2009 a 2024).
    :param consolidated_filename: Nome do arquivo .csv de saída.
    :return: DataFrame consolidado com todas as edições.
    """
    root_dir = base_dir or Path(__file__).resolve().parent.parent
    out_folder = output_dir or (root_dir / "processed")
    target_years = sorted(years) if years else SUPPORTED_YEARS
    target_filename = consolidated_filename or CONSOLIDATED_OUTPUT_FILENAME
    out_file = out_folder / target_filename

    print(f"\n========================================================")
    print(f" CONSOLIDAÇÃO DE ITENS DO ENEM ({target_years[0]}–{target_years[-1]})")
    print(f" Diretório de saída: {out_folder}")
    print(f" Arquivo consolidado: {target_filename}")
    print(f"========================================================\n")

    dfs: list[pd.DataFrame] = []
    missing_years: list[int] = []

    for y in target_years:
        year_file = out_folder / f"itens_prova_{y}_enriquecido.csv"
        if not year_file.exists():
            print(f" [AVISO] Arquivo não encontrado para {y}: {year_file.name}")
            missing_years.append(y)
            continue

        try:
            df_year = pd.read_csv(year_file, sep=';', encoding='utf-8-sig')
        except Exception:
            df_year = pd.read_csv(year_file, sep=';', encoding='latin1')

        # Assegura a coluna ANO_APLICACAO
        if 'ANO_APLICACAO' not in df_year.columns:
            df_year.insert(0, 'ANO_APLICACAO', int(y))
        else:
            df_year['ANO_APLICACAO'] = int(y)

        df_year = enforce_column_types(df_year)
        dfs.append(df_year)
        print(f" - [{y}] {len(df_year):>2} itens carregados ({year_file.name})")

    if not dfs:
        raise RuntimeError(
            f"Nenhum arquivo de ano individual foi encontrado em {out_folder} para consolidação."
        )

    # Concatena todos os DataFrames
    df_consolidated = pd.concat(dfs, ignore_index=True)

    # Aplica preservação estrita de tipos no DataFrame consolidado
    df_consolidated = enforce_column_types(df_consolidated)

    # Ordena as colunas de acordo com o padrão canônico
    ordered_cols = [c for c in CANONICAL_COLUMNS if c in df_consolidated.columns] + [
        c for c in df_consolidated.columns if c not in CANONICAL_COLUMNS
    ]
    df_consolidated = df_consolidated[ordered_cols]

    # Salva arquivo consolidado em UTF-8 com BOM e delimitador ;
    out_folder.mkdir(parents=True, exist_ok=True)
    df_consolidated.to_csv(out_file, sep=';', index=False, encoding='utf-8-sig')

    total_items = len(df_consolidated)
    reg_items = (df_consolidated['TP_APLICACAO'] == 'REGULAR').sum() if 'TP_APLICACAO' in df_consolidated.columns else 0
    ppl_items = (df_consolidated['TP_APLICACAO'] == 'REAPLICACAO_PPL').sum() if 'TP_APLICACAO' in df_consolidated.columns else 0
    img_items = df_consolidated['IN_ITEM_IMAGEM'].sum() if 'IN_ITEM_IMAGEM' in df_consolidated.columns else 0

    print(f"\n========================================================")
    print(f" CONSOLIDAÇÃO CONCLUÍDA COM SUCESSO!")
    print(f" Edições incluídas:          {len(dfs)} edições ({target_years[0]} a {target_years[-1]})")
    if missing_years:
        print(f" Edições ausentes:           {missing_years}")
    print(f" Total de itens no dataset:  {total_items}")
    print(f" Itens Prova Regular (P1):   {reg_items}")
    print(f" Itens Reaplicação/PPL (P2): {ppl_items}")
    print(f" Itens com figuras/imagens:  {int(img_items)}")
    print(f" Arquivo gerado:             {out_file}")
    print(f"========================================================\n")

    return df_consolidated

