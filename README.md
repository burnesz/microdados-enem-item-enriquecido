# Pipeline de Extração e Enriquecimento de Itens do ENEM (Matemática - MT)

Pipeline em Python para correlacionar os dados tabulares estruturados de `ITENS_PROVA_{ANO}.csv` com os cadernos de prova em formato PDF, focada na área de **Matemática (`SG_AREA = 'MT'`)**.

---

## 🎯 Proposta de Escopo

O objetivo do projeto é construir uma base consolidada e enriquecida de questões de Matemática do ENEM (2009 a 2024), **maximizando a diversidade de itens e eliminando redundâncias**:

1. **1 Cor da Prova Regular**: Seleção determinística de apenas 1 cor de caderno da Primeira Aplicação Regular (P1), sem adaptações (45 questões únicas).
2. **1 Cor da Prova de Reaplicação / PPL**: Nos anos em que houver aplicação de Reaplicação ou PPL (P2), seleção de 1 cor de caderno regular dessa aplicação, sem adaptações (45 questões inéditas).
3. **Exclusão Estrita de Provas Adaptadas e Provas Digitais**: Cadernos adaptados (Ledor, Braile, Libras, Ampliada, Superampliada, Leitor de Tela, Dosvox, NVDA) e aplicação Digital continuam excluídos.

### Comparativo de Escopo:
| Característica | Modelo Anterior (Multicores Regular) | Novo Modelo (1 Regular + 1 PPL) |
| :--- | :--- | :--- |
| **Cadernos Regulares (P1)** | 4 cores processadas (Azul, Amarelo, Cinza, Rosa) | **1 cor representativa** (ex: Amarelo ou Azul) |
| **Cadernos PPL / Reaplicação (P2)** | Excluídos | **1 cor representativa** (quando houver) |
| **Volume por Edição** | 180 linhas (45 questões repetidas 4x) | **45 a 90 questões únicas** (sem redundância de cor) |
| **Diversidade de Questões** | Apenas itens da 1ª aplicação | **Itens da 1ª aplicação + itens inéditos de PPL/Reaplicação** |

---

## 📌 Estrutura do Projeto

```text
microdados-enem-item-enriquecido/
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
│   ├── config.py                  # Constantes (MT, Dia 2), filtros de adaptação e regexes
│   ├── catalog.py                 # Catálogo estático de PDFs regulares e PPL (Ano, Aplicação, Cor) ➔ PDF
│   ├── dictionary_parser.py       # Leitor do Dicionário para identificação de provas P1 e P2
│   ├── pdf_matcher.py             # Seleção determinística de 1 cor regular e 1 cor PPL
│   ├── pdf_extractor.py           # Extração PyMuPDF de enunciados, alternativas A-E e imagens
│   └── pipeline.py                # Orquestrador da execução e geração do dataset final
│
├── processed/
│   └── itens_prova_{ANO}_enriquecido.csv  # Base final enriquecida exportada
│
├── provas_enem_2009_2024.txt      # Catálogo bruto de PDFs de provas e gabaritos
├── requirements.txt               # Dependências do projeto (pandas, openpyxl, pymupdf)
├── main.py                        # Ponto de entrada CLI
├── AGENTS.md                      # Diretrizes arquiteturais e regras para agentes de IA
└── README.md                      # Documentação geral do projeto
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

# Executar para outro ano (ex: 2023, 2022 ou 2017)
python main.py --year 2023
```

---

## 📊 Especificação das Colunas de Saída

O arquivo final exportado em `processed/itens_prova_{ANO}_enriquecido.csv` preserva as colunas originais do INEP e adiciona os campos enriquecidos:

| Coluna | Tipo | Origem | Descrição |
| :--- | :--- | :--- | :--- |
| `CO_POSICAO` | `int` | INEP | Posição da questão no caderno (1 a 45 ou 136 a 180) |
| `SG_AREA` | `str` | INEP | Sigla da área de conhecimento (`MT` para Matemática) |
| `CO_ITEM` | `int` | INEP | Código identificador universal do item no banco do INEP |
| `TX_GABARITO` | `str` | INEP | Alternativa correta (`A`, `B`, `C`, `D`, `E` ou `*` se anulada) |
| `CO_HABILIDADE` | `int` | INEP | Código da habilidade da Matriz de Referência do ENEM |
| `NU_PARAM_A/B/C`| `float`| INEP | Parâmetros psicométricos da TRI (discriminação, dificuldade, acerto ao acaso) |
| `CO_PROVA` | `int` | INEP | Código numérico da prova no INEP |
| `TX_COR` | `str` | INEP | Cor do caderno selecionado |
| `TP_APLICACAO` | `str` | Enriquecido | Categoria da prova (`REGULAR` para 1ª aplicação ou `REAPLICACAO_PPL` para 2ª aplicação) |
| `REF_ARQUIVO_PDF` | `str` | Enriquecido | Nome do PDF físico de onde o item foi extraído (identifica P1 vs P2) |
| `DESC_ENUNCIADO` | `str` | Enriquecido | Texto integral limpo do enunciado da questão |
| `DESC_ALTER_A` | `str` | Enriquecido | Texto da alternativa A |
| `DESC_ALTER_B` | `str` | Enriquecido | Texto da alternativa B |
| `DESC_ALTER_C` | `str` | Enriquecido | Texto da alternativa C |
| `DESC_ALTER_D` | `str` | Enriquecido | Texto da alternativa D |
| `DESC_ALTER_E` | `str` | Enriquecido | Texto da alternativa E |
| `IN_ITEM_IMAGEM` | `int` | Enriquecido | `1` se há imagem/gráfico no enunciado ou nas alternativas; `0` caso contrário |

> **Nota sobre Alternativas Gráficas:** Alternativas cujo conteúdo é estritamente uma figura geométrica, diagrama ou gráfico recebem o valor `[Figura / Imagem]`.

---

## 📈 Cobertura Histórica de Provas (Matemática - Dia 2)

- **Edições com Reaplicação / PPL disponível (2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2011, 2010)**:
  - 1 cor da Prova Regular (P1): 45 questões.
  - 1 cor da Prova PPL / Reaplicação (P2): 45 questões.
  - **Total**: 90 questões distintas por edição.
- **Edições sem Reaplicação / PPL no acervo oficial (2014, 2013, 2012, 2009)**:
  - 1 cor da Prova Regular (P1): 45 questões.
  - **Total**: 45 questões por edição.
- **Formato de Saída**: CSV UTF-8 com BOM (`utf-8-sig`) e delimitador `;`, garantindo abertura direta no Excel e compatibilidade com ferramentas de ciência de dados.
