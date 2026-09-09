"""
Orquestrador principal da pipeline de extração e enriquecimento dos itens do ENEM.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import time
import pandas as pd

from src.pdf_matcher import build_exam_pdf_mapping
from src.pdf_extractor import extract_questions_from_pdf

def locate_year_paths(root_dir: Path, year: int) -> Tuple[Path, Path]:
    """
    Localiza o arquivo CSV de itens e a pasta de provas em PDF para o ano informado,
    resolvendo variações de maiúsculas/minúsculas e pastas aninhadas.
    """
    year_dir = root_dir / "raw" / f"microdados_enem_{year}"
    if not year_dir.exists():
        raise FileNotFoundError(f"Diretório do ano {year} não encontrado em: {year_dir}")

    # Verifica se há pasta aninhada (ex: raw/microdados_enem_2023/microdados_enem_2023)
    nested = year_dir / f"microdados_enem_{year}"
    search_dir = nested if nested.is_dir() else year_dir

    # 1. Localização do CSV de Itens
    csv_path = None
    for p in search_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() == ".csv" and "ITENS" in p.name.upper():
            csv_path = p
            break

    if not csv_path:
        raise FileNotFoundError(f"Arquivo CSV de itens de prova não encontrado em {search_dir}")

    # 2. Localização do diretório de Provas
    provas_dir = None
    for p in search_dir.rglob("*"):
        if p.is_dir() and "PROVAS" in p.name.upper():
            provas_dir = p
            break

    if not provas_dir:
        raise FileNotFoundError(f"Diretório de cadernos de prova (PROVAS E GABARITOS) não encontrado em {search_dir}")

    return csv_path, provas_dir

def run_enem_pipeline(
    year: int = 2024,
    base_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Executa a pipeline completa para o ano especificado baseando-se exclusivamente
    no catálogo estático de cadernos e nas colunas estruturadas do arquivo ITENS_PROVA.
    """
    start_time = time.time()
    root_dir = base_dir or Path(__file__).resolve().parent.parent

    print(f"\n========================================================")
    print(f" Iniciando Pipeline ENEM - Ano: {year}")
    print(f" Diretório base: {root_dir}")
    print(f"========================================================\n")

    csv_path, provas_dir = locate_year_paths(root_dir, year)
    print(f"[1/4] Localizados arquivos de entrada:")
    print(f"      - CSV de Itens: {csv_path.name}")
    print(f"      - Pasta de Provas: {provas_dir}")

    # Carrega dados estruturados do CSV
    print(f"\n[2/4] Carregando e mapeando itens de {csv_path.name}...")
    try:
        df_itens = pd.read_csv(csv_path, sep=';', encoding='latin1')
    except Exception:
        df_itens = pd.read_csv(csv_path, sep=',', encoding='latin1')

    print(f"      Total de linhas originais no CSV: {len(df_itens)}")

    # Mapeamento determinístico de CO_PROVA -> PDF via catálogo estático
    exam_pdf_map = build_exam_pdf_mapping(provas_dir, df_itens, year)
    unique_pdfs = sorted(list(set(exam_pdf_map.values())))
    print(f"      Total de códigos de prova regulares mapeados: {len(exam_pdf_map)}")
    print(f"      Total de arquivos PDF identificados: {len(unique_pdfs)}")
    for pdf_path in unique_pdfs:
        print(f"       - {pdf_path.name}")

    if not unique_pdfs:
        raise RuntimeError(f"Nenhum arquivo PDF correspondente aos itens do ano {year} foi localizado em {provas_dir}.")

    # Extração de conteúdo dos PDFs
    print(f"\n[3/4] Extraindo enunciados, alternativas e imagens dos PDFs...")
    pdf_cache: Dict[str, Dict[Tuple[int, Optional[float]], Dict[str, Any]]] = {}
    for pdf_path in unique_pdfs:
        print(f"      Processando {pdf_path.name}...")
        extracted = extract_questions_from_pdf(pdf_path)
        pdf_cache[pdf_path.name] = extracted
        print(f"      -> {len(extracted)} questões extraídas.")

    # Enriquecimento dos dados
    print(f"\n[4/4] Enriquecendo e estruturando dados tabulares...")
    regular_codes = set(exam_pdf_map.keys())
    df_reg = df_itens[df_itens['CO_PROVA'].isin(regular_codes)].copy()
    print(f"      Total de itens regulares a enriquecer: {len(df_reg)}")

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

        pdf_path = exam_pdf_map.get(c_prova)
        pdf_name = pdf_path.name if pdf_path else ""
        ref_pdf_list.append(pdf_name)

        q_dict = pdf_cache.get(pdf_name, {})
        q_info = q_dict.get((c_pos, t_lang_key))

        # Fallback de chave caso haja divergência no indicador neutro
        if not q_info and t_lang_key is not None:
            q_info = q_dict.get((c_pos, None))
        if not q_info and t_lang_key is None:
            q_info = q_dict.get((c_pos, 0.0))

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

    df_reg['REF_ARQUIVO_PDF'] = ref_pdf_list
    df_reg['DESC_ENUNCIADO'] = enunciado_list
    df_reg['DESC_ALTER_A'] = alt_a_list
    df_reg['DESC_ALTER_B'] = alt_b_list
    df_reg['DESC_ALTER_C'] = alt_c_list
    df_reg['DESC_ALTER_D'] = alt_d_list
    df_reg['DESC_ALTER_E'] = alt_e_list
    df_reg['IN_ITEM_IMAGEM'] = tem_imagem_list

    out_folder = output_dir or (root_dir / "processed")
    out_folder.mkdir(parents=True, exist_ok=True)
    out_file = out_folder / f"itens_prova_{year}_enriquecido.csv"

    # Salva em UTF-8 com BOM e delimitador ;
    df_reg.to_csv(out_file, sep=';', index=False, encoding='utf-8-sig')

    elapsed = time.time() - start_time
    print(f"\n========================================================")
    print(f" PIPELINE CONCLUÍDA COM SUCESSO!")
    print(f" Itens processados: {len(df_reg)}")
    print(f" Taxa de correspondência: {matches_count}/{len(df_reg)} ({matches_count/len(df_reg)*100:.1f}%)")
    print(f" Itens com imagem identificada: {df_reg['IN_ITEM_IMAGEM'].sum()} ({df_reg['IN_ITEM_IMAGEM'].mean()*100:.1f}%)")
    print(f" Arquivo gerado: {out_file}")
    print(f" Tempo total: {elapsed:.2f}s")
    print(f"========================================================\n")

    return df_reg
