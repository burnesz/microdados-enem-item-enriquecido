"""
Ponto de entrada para execução da pipeline de dados do ENEM.

Uso simplificado:
    # Executa todas as edições (2009 a 2024) e todas as áreas (CN, CH, LC, MT)
    python main.py

    # Executar apenas para um ano específico (todas as áreas)
    python main.py --year 2024

    # Executar apenas para uma área (todos os anos)
    python main.py --area MT

    # Executar ano e área específicos
    python main.py --year 2024 --area MT

    # Organizar e normalizar dados brutos em raw/
    python main.py --organize
"""

import argparse
import sys
from pathlib import Path
from typing import List

# Adiciona o diretório atual ao sys.path para importação dos módulos
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from src.config import ALL_AREAS, VALID_AREAS
from src.pipeline import run_enem_pipeline, consolidate_all_years
from src.organize import organize_all_years, organize_year


def parse_years(year_arg: str) -> List[int]:
    """
    Interpreta o argumento de anos, aceitando 'all' (padrão: 2009-2024),
    ano individual (2024), intervalo (2009-2024) ou lista separada por vírgula (2020,2021).
    """
    if not year_arg or str(year_arg).lower() in ("all", "*"):
        return list(range(2009, 2025))

    year_str = str(year_arg).strip()
    if "-" in year_str:
        start_str, end_str = year_str.split("-", 1)
        return list(range(int(start_str.strip()), int(end_str.strip()) + 1))

    if "," in year_str:
        return [int(y.strip()) for y in year_str.split(",") if y.strip()]

    return [int(year_str)]


def parse_areas(area_arg: str) -> List[str]:
    """
    Interpreta o argumento de áreas, aceitando 'all' (padrão: CN, CH, LC, MT),
    área individual (MT) ou lista separada por vírgula (CN,MT).
    """
    if not area_arg or str(area_arg).strip().upper() in ("ALL", "*"):
        return list(ALL_AREAS)

    areas = [a.strip().upper() for a in str(area_arg).split(",") if a.strip()]
    invalid = [a for a in areas if a not in VALID_AREAS]
    if invalid:
        raise ValueError(f"Área(s) inválida(s): {invalid}. Áreas válidas: {VALID_AREAS}")

    return areas


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de Enriquecimento dos Microdados do ENEM (CN, CH, LC, MT — 2009 a 2024)"
    )
    parser.add_argument(
        "--year",
        type=str,
        default="all",
        help="Ano individual ou intervalo (padrão: all [2009-2024]. Ex: 2024, 2020-2024, 2021,2022)"
    )
    parser.add_argument(
        "--area",
        type=str,
        default="all",
        help="Área(s) a processar (padrão: all [CN, CH, LC, MT]. Ex: MT, CN, ou CN,MT)"
    )
    parser.add_argument(
        "--organize",
        action="store_true",
        help="Organiza pastas descompactadas, desaninha diretórios e padroniza nomes de arquivos em raw/"
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        default=None,
        help="Caminho do diretório base do projeto (opcional, padrão: diretório atual)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Caminho do diretório de saída (opcional, padrão: processed/)"
    )

    args = parser.parse_args()

    base_path = Path(args.base_dir) if args.base_dir else current_dir
    output_path = Path(args.output_dir) if args.output_dir else None

    # Modo de organização isolado
    if args.organize:
        print(f"\n========================================================")
        print(f" MODO DE ORGANIZAÇÃO — Normalização dos dados brutos em raw/")
        print(f"========================================================\n")
        organize_all_years(base_path)
        print(f"\n[OK] Organização concluída com sucesso.")
        return

    years_to_process = parse_years(args.year)
    areas_to_process = parse_areas(args.area)

    print(f"\n========================================================")
    print(f" PIPELINE ENEM — Processamento de Microdados e PDFs")
    print(f" Anos selecionados:  {years_to_process[0]} a {years_to_process[-1]} ({len(years_to_process)} anos)")
    print(f" Áreas selecionadas: {areas_to_process}")
    print(f"========================================================\n")

    summary_results = []
    errors = []

    for year in years_to_process:
        try:
            df_out = run_enem_pipeline(
                year=year,
                areas=areas_to_process,
                base_dir=base_path,
                output_dir=output_path
            )
            total_items = len(df_out)
            matched_items = (df_out['DESC_ENUNCIADO'] != "").sum()
            match_pct = (matched_items / total_items * 100.0) if total_items > 0 else 0.0
            image_items = df_out['IN_ITEM_IMAGEM'].sum()
            areas_in_df = sorted(list(df_out['SG_AREA'].unique()))

            summary_results.append({
                'ano': year,
                'areas': ', '.join(areas_in_df),
                'status': 'OK',
                'itens': total_items,
                'correspondencia': f"{matched_items}/{total_items} ({match_pct:.1f}%)",
                'imagens': int(image_items)
            })
        except Exception as e:
            print(f"\n[ERRO EM {year}] {e}\n", file=sys.stderr)
            errors.append((year, str(e)))
            summary_results.append({
                'ano': year,
                'areas': ', '.join(areas_to_process),
                'status': 'FALHA',
                'itens': 0,
                'correspondencia': '0/0 (0.0%)',
                'imagens': 0
            })

    # Se processou múltiplos anos com sucesso, consolida a base multi-ano automaticamente
    if len(years_to_process) > 1 and any(r['status'] == 'OK' for r in summary_results):
        try:
            valid_years = [r['ano'] for r in summary_results if r['status'] == 'OK']
            consolidate_all_years(
                output_dir=output_path,
                base_dir=base_path,
                years=valid_years
            )
        except Exception as e:
            print(f"\n[AVISO NA CONSOLIDAÇÃO] {e}\n", file=sys.stderr)

    # Exibe relatório final
    print(f"\n========================================================")
    print(f" RESUMO GERAL DE EXECUÇÃO")
    print(f"========================================================")
    print(f"{'Ano':<6} | {'Áreas':<16} | {'Status':<7} | {'Itens':<6} | {'Correspondência':<22} | {'Imagens':<7}")
    print("-" * 75)
    for res in summary_results:
        print(f"{res['ano']:<6} | {res['areas']:<16} | {res['status']:<7} | {res['itens']:<6} | {res['correspondencia']:<22} | {res['imagens']:<7}")
    print("=" * 75 + "\n")

    if errors:
        print(f"[ALERTA] Houve erro(s) em {len(errors)} edição(ões):")
        for yr, err in errors:
            print(f" - {yr}: {err}")
        sys.exit(1)
    else:
        print("Todas as edições e áreas selecionadas foram processadas com sucesso!")


if __name__ == "__main__":
    main()
