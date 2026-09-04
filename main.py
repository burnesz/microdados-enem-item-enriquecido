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

def main():
    parser = argparse.ArgumentParser(
        description="Pipeline de Enriquecimento dos Microdados do ENEM com Enunciados e Alternativas"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Ano do ENEM a ser processado (padrão: 2024)"
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

    try:
        run_enem_pipeline(year=args.year, base_dir=base_path, output_dir=output_path)
    except Exception as e:
        print(f"\n[ERRO NA EXECUÇÃO] {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
