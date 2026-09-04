"""
Orquestrador principal da pipeline de extração e enriquecimento dos itens do ENEM.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple, Any
import time
import pandas as pd

from src.dictionary_parser import parse_dictionary
from src.pdf_matcher import build_exam_pdf_mapping
from src.pdf_extractor import extract_questions_from_pdf

def run_enem_pipeline(
    year: int = 2024,
    base_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None
) -> pd.DataFrame:
    """
    Executa a pipeline completa para o ano especificado.
    """
    start_time = time.time()
    root_dir = base_dir or Path(__file__).resolve().parent.parent

    print(f"\n========================================================")
    print(f" Iniciando Pipeline ENEM - Ano: {year}")
    print(f" Diretório base: {root_dir}")
    print(f"========================================================\n")

    year_dir = root_dir / "raw" / f"microdados_enem_{year}"
    if not year_dir.exists():
        raise FileNotFoundError(f"Diretório do ano {year} não encontrado em: {year_dir}")

    # 1. Localização dos arquivos essenciais
    dict_candidates = list((year_dir / "DICIONÁRIO").glob("*.xlsx"))
    if not dict_candidates:
        raise FileNotFoundError(f"Arquivo de dicionário .xlsx não encontrado em {year_dir / 'DICIONÁRIO'}")
    dict_path = dict_candidates[0]

    provas_dir = year_dir / "PROVAS E GABARITOS"
    if not provas_dir.exists():
        raise FileNotFoundError(f"Diretório de provas não encontrado em {provas_dir}")

    csv_candidates = list((year_dir / "DADOS").glob(f"ITENS_PROVA_{year}.csv"))
    if not csv_candidates:
        csv_candidates = list((year_dir / "DADOS").glob("*.csv"))
    if not csv_candidates:
        raise FileNotFoundError(f"Arquivo ITENS_PROVA_{year}.csv não encontrado em {year_dir / 'DADOS'}")
    csv_path = csv_candidates[0]

    print(f"[1/5] Lendo Dicionário de Dados: {dict_path.name}")
    df_dict = parse_dictionary(dict_path, year)
    print(f"      Total de códigos de prova regulares identificados: {len(df_dict)}")

    print(f"\n[2/5] Mapeando arquivos PDF dos cadernos de prova...")
    exam_pdf_map = build_exam_pdf_mapping(provas_dir, df_dict)
    unique_pdfs = list(set(exam_pdf_map.values()))
    print(f"      {len(unique_pdfs)} cadernos PDF regulares mapeados:")
    for pdf_path in sorted(unique_pdfs):
        print(f"       - {pdf_path.name}")

    print(f"\n[3/5] Extraindo enunciados, alternativas e imagens dos PDFs...")
    pdf_cache: Dict[str, Dict[Tuple[int, Optional[float]], Dict[str, Any]]] = {}
    for pdf_path in unique_pdfs:
        print(f"      Processando {pdf_path.name}...")
        extracted = extract_questions_from_pdf(pdf_path)
        pdf_cache[pdf_path.name] = extracted
        print(f"      -> {len(extracted)} questões extraídas com sucesso.")

    print(f"\n[4/5] Carregando dados estruturados de {csv_path.name}...")
    df_itens = pd.read_csv(csv_path, sep=';', encoding='latin1')
    print(f"      Total de linhas originais no CSV: {len(df_itens)}")

    # Filtra apenas o escopo de provas regulares
    regular_codes = set(exam_pdf_map.keys())
    df_reg = df_itens[df_itens['CO_PROVA'].isin(regular_codes)].copy()
    print(f"      Total de itens filtrados (provas regulares): {len(df_reg)}")

    # 5. Enriquecimento dos dados
    print(f"\n[5/5] Realizando junção dos dados estruturados com enunciados e alternativas...")
    ref_pdf_list = []
    enunciado_list = []
    alt_a_list = []
    alt_b_list = []
    alt_c_list = []
    alt_d_list = []
    alt_e_list = []
    tem_imagem_list = []

    matches_count = 0

    for _, row in df_reg.iterrows():
        c_prova = int(row['CO_PROVA'])
        c_pos = int(row['CO_POSICAO'])
        t_lang = row['TP_LINGUA']
        t_lang_key = float(t_lang) if pd.notna(t_lang) else None

        pdf_path = exam_pdf_map.get(c_prova)
        pdf_name = pdf_path.name if pdf_path else ""
        ref_pdf_list.append(pdf_name)

        q_info = pdf_cache.get(pdf_name, {}).get((c_pos, t_lang_key))

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

    # Salva em UTF-8 com BOM para perfeita compatibilidade com Excel e ferramentas de análise
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
