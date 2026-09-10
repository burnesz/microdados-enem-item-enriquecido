 """
Ponto de entrada para execução da pipeline de dados do ENEM.

Uso:
    python main.py --year 2024
"""

import argparse
import sys
from pathlib import Path

# Adiciona o diretório atual ao sys.path para importação dos módulos
current_dir = Path(__file__).resolve().parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from src.pipeline import run_enem_pipeline

def parse_years(year_arg: str, all_flag: bool = False) -> list[int]:
    """
    Interpreta o argumento de anos, aceitando ano individual (2024),
    intervalo (2009-2024), lista separada por vírgula (2020,2021) ou flag --all.
    """
    if all_flag or str(year_arg).lower() in ("all", "*"):
        return list(range(2009, 2025))

    year_str = str(year_arg).strip()
    if "-" in year_str:
        start_str, end_str = year_str.split("-", 1)
        return list(range(int(start_str.strip()), int(end_str.strip()) + 1))

    if "," in year_str:
        return [int(y.strip()) for y in year_str.split(",") if y.strip()]

    return [int(year_str)]

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de Enriquecimento dos Microdados do ENEM (Matemática - MT)"
    )
    parser.add_argument(
        "--year",
        type=str,
        default="2024",
        help="Ano individual ou intervalo a ser processado (ex: 2024 ou 2009-2024)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Executar para todas as edições suportadas (2009 a 2024)"
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

    years_to_process = parse_years(args.year, all_flag=args.all)
    print(f"\n========================================================")
    print(f" PIPELINE ENEM — Processamento de Matemática (MT)")
    print(f" Anos selecionados: {years_to_process}")
    print(f"========================================================\n")

    summary_results = []
    errors = []

    for year in years_to_process:
        try:
            df_out = run_enem_pipeline(year=year, base_dir=base_path, output_dir=output_path)
            total_items = len(df_out)
            matched_items = (df_out['DESC_ENUNCIADO'] != "").sum()
            match_pct = (matched_items / total_items * 100.0) if total_items > 0 else 0.0
            image_items = df_out['IN_ITEM_IMAGEM'].sum()
            summary_results.append({
                'ano': year,
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
                'status': 'FALHA',
                'itens': 0,
                'correspondencia': '0.0%',
                'imagens': 0
            })

    print(f"\n========================================================")
    print(f" RESUMO GERAL DE EXECUÇÃO (2009–2024)")
    print(f"========================================================")
    print(f"{'Ano':<6} | {'Status':<7} | {'Itens':<6} | {'Correspondência':<22} | {'Imagens':<8}")
    print("-" * 60)
    for res in summary_results:
        print(f"{res['ano']:<6} | {res['status']:<7} | {res['itens']:<6} | {res['correspondencia']:<22} | {res['imagens']:<8}")
    print("=" * 60)

    if errors:
        print(f"\nOcorreram erros nos seguintes anos: {[y for y, _ in errors]}")
        sys.exit(1)
    else:
        print(f"\nTodas as edições selecionadas foram processadas com sucesso!")

if __name__ == "__main__":
    main()

