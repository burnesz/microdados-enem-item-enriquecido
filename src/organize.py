"""
Módulo para organização, desaninhamento e padronização automática dos arquivos brutos do ENEM.

Resolve:
1. Pastas aninhadas decorrentes de descompactação (ex: microdados_enem_2023/microdados_enem_2023/...).
2. Correção de extensões duplicadas (ex: .pdf.pdf para .pdf em 2015).
3. Renomeação de arquivos avulsos baixados manualmente (como cadernos PPL de 2012-2014) para os nomes canônicos
   oficiais reconhecidos pelo ecossistema, utilizando o leitor de folha de rosto (Fingerprinting).
"""

from pathlib import Path
import shutil
from typing import Dict, List, Optional, Tuple, Any

from src.catalog import EXAM_PDF_CATALOG, normalize_color
from src.pdf_fingerprint import inspect_exam_pdf


def flatten_nested_folder(year_dir: Path, year: int) -> bool:
    """
    Detecta e achata pastas aninhadas causadas por descompactação duplicada
    (ex: raw/microdados_enem_2023/microdados_enem_2023/ -> raw/microdados_enem_2023/).
    """
    nested_dir = year_dir / f"microdados_enem_{year}"
    if not nested_dir.is_dir():
        return False

    print(f"  [Achatando] Normalizando pasta aninhada em {year_dir.name}...")
    # Move todos os itens de dentro da pasta aninhada para year_dir
    for item in list(nested_dir.iterdir()):
        dest = year_dir / item.name
        if dest.exists():
            if dest.is_dir():
                # Mescla diretórios
                for sub in list(item.iterdir()):
                    sub_dest = dest / sub.name
                    if not sub_dest.exists():
                        shutil.move(str(sub), str(sub_dest))
                try:
                    item.rmdir()
                except Exception:
                    pass
            continue
        shutil.move(str(item), str(dest))

    try:
        nested_dir.rmdir()
    except Exception:
        pass

    return True


def fix_double_extensions(provas_dir: Path) -> List[Tuple[Path, Path]]:
    """
    Corrige arquivos com extensões duplicadas conhecidas (ex: .pdf.pdf para .pdf).
    """
    renamed = []
    for f in list(provas_dir.rglob("*.pdf.pdf")):
        new_name = f.name[:-4]  # Remove os últimos 4 caracteres (.pdf)
        dest = f.parent / new_name
        if not dest.exists():
            f.rename(dest)
            renamed.append((f, dest))
            print(f"  [Extensão Corrigida] {f.name} -> {dest.name}")
    return renamed


def standardize_provas_filenames(provas_dir: Path, year: int) -> List[Tuple[Path, Path]]:
    """
    Inspeciona os PDFs na pasta de provas e renomeia automaticamente arquivos não padronizados
    (como provas de reaplicação/PPL baixadas avulsas) para a nomenclatura canônica oficial.
    """
    year_catalog = EXAM_PDF_CATALOG.get(year, {})
    renamed = []

    for ext in ("*.pdf", "*.PDF"):
        for pdf_path in list(provas_dir.rglob(ext)):
            # Ignora extensões duplicadas ainda não tratadas
            if pdf_path.name.endswith(".pdf.pdf"):
                continue

            info = inspect_exam_pdf(pdf_path)
            if not info:
                continue

            # O catálogo canônico só cobre o 2º dia: cadernos do 1º dia (pelo nome ou pela capa)
            # nunca são renomeados (ex.: 2017, onde o 1º dia virava CAD_05_DIA_2_AMARELO)
            if info['day'] != 2 or info.get('cover_day') not in (2, None):
                continue

            app = info['app']
            color = info['color']
            canonical_name = year_catalog.get((app, 2, color))

            if not canonical_name:
                continue

            # Se o arquivo já possui exatamente o nome canônico (case-insensitive), mantém
            if pdf_path.name.lower() == canonical_name.lower():
                continue

            dest_path = pdf_path.parent / canonical_name
            # Evita sobrescrever se o destino já existir
            if not dest_path.exists():
                pdf_path.rename(dest_path)
                renamed.append((pdf_path, dest_path))
                print(f"  [Renomeado Canônico] {pdf_path.name} -> {canonical_name}")

    return renamed


def organize_year(year_dir: Path, year: int) -> Dict[str, Any]:
    """
    Executa todas as rotinas de normalização e organização para a pasta de uma edição específica:
    1. Achata diretórios aninhados.
    2. Corrige extensões duplas.
    3. Padroniza nomes de cadernos Dia 2 para as convenções canônicas.
    """
    if not year_dir.exists():
        return {'status': 'not_found', 'year': year}

    print(f"\n========================================================")
    print(f" Organizando dados brutos do ENEM {year}: {year_dir.name}")
    print(f"========================================================")

    # 1. Achatamento de pastas aninhadas
    flattened = flatten_nested_folder(year_dir, year)

    # 2. Localiza pasta de provas
    provas_dirs = [d for d in year_dir.rglob("*") if d.is_dir() and "PROVA" in d.name.upper()]
    if not provas_dirs:
        print(f"  [Aviso] Nenhuma pasta de provas localizada em {year_dir.name}.")
        return {'status': 'no_provas_dir', 'year': year}

    double_ext_fixed = []
    canonically_renamed = []

    for pd in provas_dirs:
        # Corrige .pdf.pdf
        double_ext_fixed.extend(fix_double_extensions(pd))
        # Padroniza nomes
        canonically_renamed.extend(standardize_provas_filenames(pd, year))

    print(f"  -> Concluído ENEM {year}: {len(double_ext_fixed)} extensões corrigidas, {len(canonically_renamed)} renomeações canônicas.")

    return {
        'status': 'ok',
        'year': year,
        'flattened': flattened,
        'double_ext_fixed': len(double_ext_fixed),
        'canonically_renamed': len(canonically_renamed)
    }


def organize_all_years(base_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Percorre todas as pastas microdados_enem_YYYY em raw/ e executa a organização.
    """
    root = base_dir or Path(__file__).resolve().parent.parent
    raw_dir = root / "raw"
    results = []

    if not raw_dir.exists():
        print(f"[Aviso] Diretório raw não encontrado em {raw_dir}")
        return results

    for year_dir in sorted(raw_dir.glob("microdados_enem_*")):
        try:
            year = int(year_dir.name.split("_")[-1])
        except (ValueError, IndexError):
            continue

        res = organize_year(year_dir, year)
        results.append(res)

    return results
