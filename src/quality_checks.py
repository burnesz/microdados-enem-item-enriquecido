"""
Checagens de regressão da transcrição PDF → texto, aplicadas a cada item exportado.

Cada regra devolve uma ocorrência (regra, coluna, trecho) quando encontra um padrão típico de
corrupção da extração: alternativas repetidas ou truncadas, LaTeX mal delimitado, estruturas
vazias de matrizes/frações desmontadas, índices descolados do símbolo, sobra de texto depois da
pergunta, enunciado curto demais e dependência de figura sem descrição.

As regras são heurísticas: um item sinalizado deve ser conferido no PDF e, se estiver correto,
registrado em `REVISADOS_MANUALMENTE`.
"""

import re
from typing import Dict, List, Tuple

import pandas as pd


# Itens conferidos no PDF que disparam uma checagem sem estarem corrompidos: {CO_ITEM: (regras, motivo)}
REVISADOS_MANUALMENTE: Dict[int, Tuple[Tuple[str, ...], str]] = {
    72821: (("enunciado_minimo",), "Enunciado do caderno tem só uma frase; não há figura nem texto faltando."),
}

ALTERNATIVE_COLUMNS = [f"DESC_ALTER_{letra}" for letra in "ABCDE"]
TEXT_COLUMNS = ["DESC_ENUNCIADO"] + ALTERNATIVE_COLUMNS

MIN_ENUNCIADO_CHARS = 120
# Sobra curta depois do último "?" é lixo da extração; texto longo é continuação legítima
# (ex.: "?" no título de uma fonte citada antes do comando).
MAX_SOBRA_APOS_PERGUNTA = 80

# Cifrões monetários (R$, US$, U$) e escapados não delimitam LaTeX.
_LITERAL_DOLLAR_RE = re.compile(r"\b(?:R|US|U)\$|\\\$")
_MATH_SEGMENT_RE = re.compile(r"\$([^$]*)\$")
# Duas palavras comuns seguidas (sem comando LaTeX antes) dentro de $...$.
_PLAIN_WORDS_RE = re.compile(r"(?<![\\A-Za-zÀ-ÿ])[A-Za-zÀ-ÿ]{3,}\s+[a-zà-ÿ]{2,}(?![A-Za-zÀ-ÿ{])")

_EMPTY_STRUCTURE_RE = re.compile(r"\(\s*\)|\{\s*\}|\\left\s*[(\[]\s*\\right\s*[)\]]")

# x < x < x, X = X > X, X e X: o mesmo símbolo repetido, sem índice.
_REPEATED_SYMBOL_RE = re.compile(
    r"(?<![\w\\{$])([A-Za-z])\s*(?:[<>=≤≥]|\\le|\\ge|\\leq|\\geq)\s*\1\s*(?:[<>=≤≥]|\\le|\\ge|\\leq|\\geq)\s*\1(?![\w_])"
    r"|(?<![\w\\{$])(?<!\ba )([A-Za-z])\s*,?\s+e\s+\2(?![\w_])(?!\s+a\s)"
)
# Letra isolada seguida de dígitos soltos (p . 1 2 3, S . 1 1 2 2) ou 3+ dígitos soltos em sequência.
_LOOSE_INDEX_RE = re.compile(
    r"(?<![\w\\{$])[A-Za-z]\s*[.,]?\s+(?<![\d,])\d(?:\s+\d(?![\d,]))+(?![\d,])"
    r"|(?<![\d,.\w])\d(?:\s\d(?![\d,.])){2,}(?![\d,.])"
)
# Sequências de letras soltas no fim da linha (A C B, B A C) que sobram dos índices.
_LOOSE_LETTERS_RE = re.compile(r"(?:^|\s)([A-Z])\s([A-Z])\s([A-Z])(?:\s|$)")

_VISUAL_MENTION_RE = re.compile(
    r"\b(figura|imagem|gráfico|grafico|ilustraç\w+|ilustrad\w+|croqui|mapa|planta baixa|esquema a seguir)\b",
    re.IGNORECASE,
)


def _strip_text(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip()


def _without_tables(texto: str) -> str:
    return "\n".join(linha for linha in texto.split("\n") if not linha.lstrip().startswith("|"))


def _dollar_inside_braces(texto: str) -> bool:
    depth = 0
    escaped = False
    for ch in texto:
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(depth - 1, 0)
        elif ch == "$" and depth > 0:
            return True
    return False


def check_item(row: pd.Series) -> List[Dict[str, str]]:
    """Aplica as 8 regras a um item e devolve as ocorrências encontradas."""
    ocorrencias: List[Dict[str, str]] = []

    def flag(regra: str, coluna: str, trecho: str) -> None:
        ocorrencias.append({"regra": regra, "coluna": coluna, "trecho": trecho[:120]})

    textos = {col: _strip_text(row.get(col)) for col in TEXT_COLUMNS}
    alternativas = [textos[col] for col in ALTERNATIVE_COLUMNS]

    # 1. Alternativas distintas
    if len(set(alternativas)) < 5:
        repetidas = sorted({a for a in alternativas if alternativas.count(a) > 1})
        flag("alternativas_distintas", "DESC_ALTER_*", " | ".join(repetidas))

    # 2. Alternativa não vazia e não truncada
    for col in ALTERNATIVE_COLUMNS:
        alt = textos[col]
        if not re.sub(r"[\s\W_]", "", alt):
            flag("alternativa_vazia_ou_truncada", col, alt)
        elif alt[0] in ",;:":
            flag("alternativa_vazia_ou_truncada", col, alt)

    for col, texto in textos.items():
        if not texto:
            continue
        sem_literais = _LITERAL_DOLLAR_RE.sub("", texto)

        # 3. Delimitadores LaTeX balanceados, sem $ dentro de {...} e sem texto comum em $...$
        if sem_literais.count("$") % 2:
            flag("latex_desbalanceado", col, texto)
        elif _dollar_inside_braces(sem_literais):
            flag("latex_dolar_em_chaves", col, texto)
        else:
            for seg in _MATH_SEGMENT_RE.findall(sem_literais):
                # Texto em \text{...}, índices e expoentes ('V_{tronco de cone}') é legítimo
                m = _PLAIN_WORDS_RE.search(re.sub(r"\\(?:text|mathrm|operatorname)\{[^}]*\}|[_^]\{[^}]*\}", "", seg))
                if m:
                    flag("latex_texto_comum", col, seg)
                    break

        corpo = _without_tables(sem_literais)

        # 4. Estruturas vazias
        m = _EMPTY_STRUCTURE_RE.search(corpo)
        if m:
            flag("estrutura_vazia", col, corpo[max(m.start() - 30, 0):m.end() + 30])

        # 5. Índices soltos
        for regex in (_REPEATED_SYMBOL_RE, _LOOSE_INDEX_RE, _LOOSE_LETTERS_RE):
            m = regex.search(corpo)
            if m:
                flag("indice_solto", col, corpo[max(m.start() - 30, 0):m.end() + 30])
                break

    enunciado = textos["DESC_ENUNCIADO"]
    corpo_enunciado = _without_tables(enunciado)

    # 6. Texto após a pergunta
    if "?" in corpo_enunciado:
        resto = corpo_enunciado.rsplit("?", 1)[1]
        if re.sub(r"[\s\W_]", "", resto) and len(resto.strip()) <= MAX_SOBRA_APOS_PERGUNTA:
            flag("texto_apos_pergunta", "DESC_ENUNCIADO", resto.strip())

    # 7. Enunciado mínimo
    if len(enunciado) < MIN_ENUNCIADO_CHARS:
        flag("enunciado_minimo", "DESC_ENUNCIADO", enunciado)

    # 8. Dependência visual sem marcação de imagem
    if int(row.get("IN_ITEM_IMAGEM") or 0) == 0:
        m = _VISUAL_MENTION_RE.search(enunciado)
        if m:
            flag("dependencia_visual", "DESC_ENUNCIADO", enunciado[max(m.start() - 40, 0):m.end() + 40])

    revisado = REVISADOS_MANUALMENTE.get(int(row.get("CO_ITEM"))) if pd.notna(row.get("CO_ITEM")) else None
    if revisado:
        ocorrencias = [o for o in ocorrencias if o["regra"] not in revisado[0]]
    return ocorrencias


def run_quality_checks(df: pd.DataFrame) -> pd.DataFrame:
    """Devolve uma linha por ocorrência, com a identificação do item."""
    id_cols = [c for c in ("CO_ITEM", "ANO_APLICACAO", "CO_POSICAO", "CO_HABILIDADE", "REF_ARQUIVO_PDF") if c in df.columns]
    linhas = []
    for _, row in df.iterrows():
        for ocorrencia in check_item(row):
            linhas.append({**{c: row[c] for c in id_cols}, **ocorrencia})
    return pd.DataFrame(linhas, columns=id_cols + ["regra", "coluna", "trecho"])
