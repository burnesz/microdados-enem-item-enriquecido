"""
Orquestrador principal da pipeline de extração e enriquecimento dos itens do ENEM.
Focado exclusivamente na área de Matemática (MT) com resolução dinâmica pelo Dicionário
e seleção unária determinística de cadernos (1 cor da Prova Regular + 1 cor de Reaplicação/PPL).
"""

from pathlib import Path
from typing import Dict, Optional, Tuple, Any, Union, List
import time
import pandas as pd

from src.config import (
    ALL_AREAS,
    TARGET_AREA,
    SUPPORTED_YEARS,
    CONSOLIDATED_OUTPUT_FILENAME,
    LLM_TEXT_OUTPUT_FILENAME,
    CANONICAL_COLUMNS,
    INTEGER_COLUMNS,
    FLOAT_COLUMNS
)
from src.dictionary_parser import parse_exam_codes, parse_math_exam_codes
from src.pdf_matcher import build_selected_exams, build_selected_math_exams
from src.pdf_extractor import extract_questions_from_pdf
from src.organize import organize_year

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
    Executa a rotina de organização/achatamento automático se necessário.
    """
    year_dir = root_dir / "raw" / f"microdados_enem_{year}"
    if not year_dir.exists():
        raise FileNotFoundError(f"Diretório do ano {year} não encontrado em: {year_dir}")

    # Organiza e desaninha previamente de forma automática
    organize_year(year_dir, year)

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
    areas: Optional[Union[str, list[str]]] = None,
    base_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Executa a pipeline de enriquecimento para o ano e áreas informadas:
    1. Localiza CSV de itens, pasta de provas e Dicionário de Dados (.xlsx).
    2. Lê o Dicionário dinamicamente para classificar códigos das provas em Regular (P1) e PPL (P2).
    3. Seleciona deterministicamente 1 caderno Regular e 1 caderno PPL (quando houver).
    4. Extrai enunciados, alternativas (A-E) e presença de imagem via PyMuPDF com cache de cadernos.
    5. Filtra e enriquece os itens das áreas solicitadas (padrão: todas as 4 áreas).
    6. Exporta a base enriquecida em processed/itens_prova_{ANO}_enriquecido.csv.
    """
    start_time = time.time()
    root_dir = base_dir or Path(__file__).resolve().parent.parent

    # Normalização da lista de áreas alvo
    if areas is None or (isinstance(areas, str) and areas.strip().upper() in ('ALL', '*')):
        target_areas = list(ALL_AREAS)
    elif isinstance(areas, str):
        target_areas = [a.strip().upper() for a in areas.split(',') if a.strip()]
    else:
        target_areas = [a.strip().upper() for a in areas]

    print(f"\n========================================================")
    print(f" Iniciando Pipeline ENEM - Ano: {year}")
    print(f" Áreas selecionadas: {target_areas}")
    print(f" Escopo: 1 Cor Regular (P1) + 1 Cor Reaplicação/PPL (P2)")
    print(f" Diretório base: {root_dir}")
    print(f"========================================================\n")

    csv_path, provas_dir, dict_path = locate_year_paths(root_dir, year)
    print(f"[1/4] Localizados arquivos de entrada:")
    print(f"      - CSV de Itens: {csv_path.name}")
    print(f"      - Dicionário:   {dict_path.name}")
    print(f"      - Pasta Provas: {provas_dir}")

    # 1. Carrega dados estruturados do CSV de itens
    print(f"\n[2/4] Carregando itens de prova...")
    try:
        df_itens_all = pd.read_csv(csv_path, sep=';', encoding='latin1')
    except Exception:
        df_itens_all = pd.read_csv(csv_path, sep=',', encoding='latin1')

    print(f"      Total de linhas no CSV original: {len(df_itens_all)}")

    pdf_cache: Dict[str, Dict[Tuple[int, Optional[float]], Dict[str, Any]]] = {}
    enriched_areas_dfs = []
    area_summaries = []

    print(f"\n[3/4] Mapeando cadernos, extraindo PDFs e enriquecendo áreas...")

    for area in target_areas:
        print(f"\n      >>> Processando Área: {area} <<<")
        df_itens_area = df_itens_all[df_itens_all['SG_AREA'] == area].copy()
        if df_itens_area.empty:
            print(f"      [Aviso] Nenhum item para área {area} encontrado no CSV.")
            continue

        try:
            df_dict_area = parse_exam_codes(dict_path, area=area, csv_path=csv_path)
        except Exception as e:
            print(f"      [Aviso] Falha ao ler dicionário para {area}: {e}")
            continue

        selected_exams = build_selected_exams(provas_dir, df_dict_area, year, area=area)
        if not selected_exams:
            print(f"      [Aviso] Nenhum caderno para a área {area} foi localizado fisicamente.")
            continue

        exam_pdf_map: Dict[int, Path] = {c: info['pdf_path'] for c, info in selected_exams.items()}
        exam_app_map: Dict[int, str] = {c: info['tp_aplicacao'] for c, info in selected_exams.items()}

        for co_prova, info in selected_exams.items():
            print(f"       - [{info['tp_aplicacao']}] Código {co_prova} ({info['tx_cor']}): {info['pdf_path'].name}")
            pdf_path = info['pdf_path']
            if pdf_path.name not in pdf_cache:
                print(f"         Extraindo conteúdo de {pdf_path.name}...")
                extracted = extract_questions_from_pdf(pdf_path)
                pdf_cache[pdf_path.name] = extracted
                print(f"         -> {len(extracted)} questões extraídas.")

        # Enriquecimento dos itens da área
        selected_codes = set(selected_exams.keys())
        df_reg = df_itens_area[df_itens_area['CO_PROVA'].isin(selected_codes)].copy()

        tp_aplicacao_list = []
        ref_pdf_list = []
        enunciado_list = []
        alt_a_list = []
        alt_b_list = []
        alt_c_list = []
        alt_d_list = []
        alt_e_list = []
        tem_imagem_list = []
        tem_tabela_list = []

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

            # Resolução de offset
            target_pos = c_pos
            if target_pos <= 45 and not any(k[0] == target_pos for k in q_dict.keys()):
                if any(k[0] == target_pos + 135 for k in q_dict.keys()):
                    target_pos = target_pos + 135
                elif any(k[0] == target_pos + 90 for k in q_dict.keys()):
                    target_pos = target_pos + 90
                elif any(k[0] == target_pos + 45 for k in q_dict.keys()):
                    target_pos = target_pos + 45

            q_info = q_dict.get((target_pos, t_lang_key))
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
                tem_tabela_list.append(q_info['IN_ITEM_TABELA'])
            else:
                enunciado_list.append("")
                alt_a_list.append("")
                alt_b_list.append("")
                alt_c_list.append("")
                alt_d_list.append("")
                alt_e_list.append("")
                tem_imagem_list.append(0)
                tem_tabela_list.append(0)

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
        df_reg['IN_ITEM_TABELA'] = tem_tabela_list

        pct = (matches_count / len(df_reg) * 100.0) if len(df_reg) > 0 else 0.0
        area_summaries.append({
            'area': area,
            'itens': len(df_reg),
            'matches': matches_count,
            'pct': pct,
            'imagens': df_reg['IN_ITEM_IMAGEM'].sum()
        })
        print(f"      -> {matches_count}/{len(df_reg)} ({pct:.1f}%) itens enriquecidos para {area}.")
        enriched_areas_dfs.append(df_reg)

    if not enriched_areas_dfs:
        raise RuntimeError(f"Nenhum item enriquecido para {year} nas áreas {target_areas}.")

    df_combined = pd.concat(enriched_areas_dfs, ignore_index=True)
    ordered_cols = [c for c in CANONICAL_COLUMNS if c in df_combined.columns] + [
        c for c in df_combined.columns if c not in CANONICAL_COLUMNS
    ]
    df_combined = df_combined[ordered_cols]
    df_combined = enforce_column_types(df_combined)

    out_folder = output_dir or (root_dir / "processed")
    out_folder.mkdir(parents=True, exist_ok=True)

    if target_areas == ['MT']:
        out_file = out_folder / f"itens_prova_{year}_enriquecido.csv"
    elif len(target_areas) == 1:
        out_file = out_folder / f"itens_prova_{year}_{target_areas[0].lower()}_enriquecido.csv"
    else:
        out_file = out_folder / f"itens_prova_{year}_enriquecido.csv"

    df_combined.to_csv(out_file, sep=';', index=False, encoding='utf-8-sig')

    elapsed = time.time() - start_time
    total_items = len(df_combined)
    total_matches = sum(s['matches'] for s in area_summaries)
    match_pct = (total_matches / total_items * 100.0) if total_items > 0 else 0.0

    print(f"\n========================================================")
    print(f" PIPELINE ENEM CONCLUÍDA COM SUCESSO!")
    print(f" Edição (Ano):                 {year}")
    print(f" Áreas processadas:            {', '.join([s['area'] for s in area_summaries])}")
    print(f" Total de itens enriquecidos:  {total_items}")
    print(f" Taxa de correspondência:      {total_matches}/{total_items} ({match_pct:.1f}%)")
    print(f" Arquivo gerado:               {out_file}")
    print(f" Tempo total:                  {elapsed:.2f}s")
    print(f"========================================================\n")

    return df_combined


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
    tab_items = df_consolidated['IN_ITEM_TABELA'].sum() if 'IN_ITEM_TABELA' in df_consolidated.columns else 0

    print(f"\n========================================================")
    print(f" CONSOLIDAÇÃO CONCLUÍDA COM SUCESSO!")
    print(f" Edições incluídas:          {len(dfs)} edições ({target_years[0]} a {target_years[-1]})")
    if missing_years:
        print(f" Edições ausentes:           {missing_years}")
    print(f" Total de itens no dataset:  {total_items}")
    print(f" Itens Prova Regular (P1):   {reg_items}")
    print(f" Itens Reaplicação/PPL (P2): {ppl_items}")
    print(f" Itens com figuras/imagens:  {int(img_items)}")
    print(f" Itens com tabelas em texto: {int(tab_items)}")
    print(f" Arquivo gerado:             {out_file}")
    print(f"========================================================\n")

    return df_consolidated



def export_llm_text_items(
    output_dir: Optional[Path] = None,
    base_dir: Optional[Path] = None,
    output_filename: Optional[str] = None
) -> pd.DataFrame:
    """
    Gera, a partir da base consolidada, o subconjunto de itens aproveitáveis por um LLM somente texto:
    CO_HABILIDADE preenchido, IN_ITEM_ABAN = 0 e IN_ITEM_IMAGEM = 0.
    """
    root_dir = base_dir or Path(__file__).resolve().parent.parent
    out_folder = output_dir or (root_dir / "processed")
    source_file = out_folder / CONSOLIDATED_OUTPUT_FILENAME
    out_file = out_folder / (output_filename or LLM_TEXT_OUTPUT_FILENAME)

    if not source_file.exists():
        raise FileNotFoundError(f"Base consolidada não encontrada: {source_file}")

    df = enforce_column_types(pd.read_csv(source_file, sep=';', encoding='utf-8-sig'))
    mask = (
        df['CO_HABILIDADE'].notna()
        & (df['IN_ITEM_ABAN'] == 0)
        & (df['IN_ITEM_IMAGEM'] == 0)
    )
    df_llm = df[mask].reset_index(drop=True)
    df_llm.to_csv(out_file, sep=';', index=False, encoding='utf-8-sig')

    print(f" Subconjunto LLM texto: {len(df_llm)} de {len(df)} itens -> {out_file}")

    return df_llm
