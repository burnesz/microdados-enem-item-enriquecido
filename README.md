# Pipeline de Extração e Enriquecimento de Itens do ENEM (Matemática - MT)

Pipeline em Python para correlacionar os dados estruturados de `ITENS_PROVA_{ANO}.csv` com os enunciados e alternativas contidos nos cadernos de prova em formato PDF, focada na área de **Matemática (`SG_AREA = 'MT'`)**.

A pipeline realiza uma **busca dinâmica pela variável `CO_PROVA_MT` em todas as abas do Dicionário de Dados (`.xlsx`)**, cruza com os códigos de prova regulares da 1ª Aplicação, resolve os arquivos físicos via catálogo estático de PDFs (Dia 2) e extrai via PyMuPDF os enunciados, alternativas A–E e detecção espacial de imagens.

---

## 📌 Estrutura do Projeto

```text
microdados_enem/
│
├── .venv/                         # Ambiente virtual Python
├── raw/                           # Dados brutos dos microdados (INEP 2009 a 2024)
│   ├── microdados_enem_2024/
│   │   ├── DADOS/ITENS_PROVA_2024.csv
│   │   ├── DICIONÁRIO/Dicionário_Microdados_Enem_2024.xlsx
│   │   └── PROVAS E GABARITOS/*.pdf
│   └── ...
│
├── src/
│   ├── __init__.py
│   ├── config.py                  # Constantes (MT, Dia 2), filtros de exclusão e regexes
│   ├── catalog.py                 # Catálogo estático oficial de PDFs (Ano, Dia, Cor) ➔ PDF
│   ├── dictionary_parser.py       # Leitor dinâmico do dicionário Excel (CO_PROVA_MT em qualquer aba)
│   ├── pdf_matcher.py             # Mapeamento determinístico de CO_PROVA ➔ PDF físico (com busca recursiva)
│   ├── pdf_extractor.py           # Extração PyMuPDF de enunciados, alternativas e detecção de imagem
│   └── pipeline.py                # Orquestrador da execução e geração do dataset final
│
├── processed/
│   └── itens_prova_{ANO}_enriquecido.csv  # Base enriquecida exportada
│
├── requirements.txt               # Dependências do projeto (pandas, openpyxl, pymupdf)
├── main.py                        # Ponto de entrada CLI
├── AGENTS.md                      # Diretrizes arquiteturais para agentes LLM
└── README.md
```

---

## 🚀 Como Executar

### 1. Ativar o Ambiente Virtual
No Linux / WSL:
```bash
source .venv/bin/activate
```

No Windows PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Executar a Pipeline
```bash
# Execução padrão (ano 2024)
python main.py --year 2024

# Executar para outro ano (ex: 2017 ou 2009)
python main.py --year 2017
```

---

## 📊 Novas Colunas Adicionadas

Além das colunas originais do INEP (`CO_POSICAO`, `SG_AREA`, `CO_ITEM`, `TX_GABARITO`, `CO_HABILIDADE`, `TX_COR`, `CO_PROVA`, `TP_LINGUA`, etc.), foram adicionadas:

| Coluna | Tipo | Descrição | Exemplo |
| :--- | :--- | :--- | :--- |
| `REF_ARQUIVO_PDF` | `str` | Nome do arquivo PDF do caderno de prova de onde os dados foram extraídos | `ENEM_2024_P1_CAD_07_DIA_2_AZUL.pdf` |
| `DESC_ENUNCIADO` | `str` | Texto completo do enunciado da questão limpo | `"Uma sala com piso no formato retangular..."` |
| `DESC_ALTER_A` | `str` | Texto da alternativa A | `"I."` |
| `DESC_ALTER_B` | `str` | Texto da alternativa B | `"II."` |
| `DESC_ALTER_C` | `str` | Texto da alternativa C | `"III."` |
| `DESC_ALTER_D` | `str` | Texto da alternativa D | `"IV."` |
| `DESC_ALTER_E` | `str` | Texto da alternativa E | `"V."` |
| `IN_ITEM_IMAGEM` | `int` | Indicador binário (`1` se a questão contém imagem no enunciado/alternativas, `0` caso contrário) | `1` ou `0` |

> **Nota:** Alternativas cujo conteúdo é estritamente gráfico (ex: figuras geométricas, diagramas, gráficos) são identificadas como `[Figura / Imagem]`.

---

## 📈 Resultados da Validação (Matemática - MT)

- **Escopo**: 100% focado em Matemática (`SG_AREA == 'MT'`).
- **Total de Itens Regulares por Edição Regular**: 180 itens (4 cadernos x 45 questões).
- **Taxa de Correspondência**: 100.0% em todas as edições testadas (2024, 2021, 2017, 2009).
- **Tratamento de Indexação Histórica**: Compatibilidade automática com edições indexadas de 1 a 45 (como 2017) e de 136 a 180 (demais anos).
- **Formato de Saída**: CSV UTF-8 com BOM (`utf-8-sig`) separado por `;`, compatível nativamente com Excel e bibliotecas analíticas.
