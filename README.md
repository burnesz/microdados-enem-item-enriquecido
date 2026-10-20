# Base Enriquecida de Itens do ENEM (CN, CH, LC, MT — 2009 a 2024)

Pipeline de dados automatizada para unir os microdados tabulares psicométricos oficiais do INEP com o conteúdo textual e gráfico dos cadernos de prova em formato PDF, cobrindo todas as 4 áreas do conhecimento do ENEM:
- **`MT`**: Matemática e suas Tecnologias
- **`CN`**: Ciências da Natureza e suas Tecnologias (Física, Química, Biologia)
- **`CH`**: Ciências Humanas e suas Tecnologias (História, Geografia, Filosofia, Sociologia)
- **`LC`**: Linguagens, Códigos e suas Tecnologias (Língua Portuguesa, Literatura, Artes, Educação Física e Língua Estrangeira: Inglês/Espanhol)

O resultado final é uma base consolidada com **mais de 5.000 itens calibrados pela TRI (Teoria de Resposta ao Item)**, contendo enunciados limpos, alternativas separadas (A a E), parâmetros psicométricos oficiais, opções de língua estrangeira e indicador de presença de figuras/gráficos.

---

## 🎯 Metodologia e Escopo

Cada edição do ENEM aplica cadernos regulares (ex: Azul, Amarelo, Branco, Rosa, Cinza) que contêm **as mesmas questões** em ordens distintas. Além disso, a partir de 2010, o INEP realiza uma segunda aplicação (Reaplicação / PPL — Pessoas Privadas de Liberdade) com **questões inéditas**.

Para maximizar a diversidade de itens e eliminar redundâncias, este projeto adota uma **amostragem unária representativa por aplicação**:

1. **1 Cor da Prova Regular (1ª Aplicação — P1)**: 45 questões por área por edição.
2. **1 Cor da Prova de Reaplicação / PPL (2ª Aplicação — P2)**: 45 questões inéditas por área por edição (quando houver).
3. **Exclusão Estrita de Provas Adaptadas e Digitais**: São excluídos cadernos adaptados (Ledor, Braile, Libras, Ampliada, Superampliada, Leitor de Tela) e aplicações exclusivamente digitais (2020 a 2022).

### Mapeamento Histórico de Dias por Área
O ENEM sofreu uma inversão de calendário em 2017 que a pipeline resolve dinamicamente:
- **Edições 2009 a 2016**:
  - **Dia 1 (Sábado)**: Ciências Humanas (`CH`, Q1 a 45) + Ciências da Natureza (`CN`, Q46 a 90).
  - **Dia 2 (Domingo)**: Linguagens e Códigos (`LC`, Q91 a 135) + Matemática (`MT`, Q136 a 180).
- **Edições 2017 a 2024**:
  - **Dia 1 (1º Domingo)**: Linguagens e Códigos (`LC`, Q1 a 45) + Ciências Humanas (`CH`, Q46 a 90).
  - **Dia 2 (2º Domingo)**: Ciências da Natureza (`CN`, Q91 a 135) + Matemática (`MT`, Q136 a 180).

---

## 🚀 Como Executar (CLI Simplificada)

O sistema foi desenhado para ter **uso imediato e intuitivo**:

### Execução Padrão (Gera Tudo)
```bash
# Executa automaticamente todas as 16 edições (2009 a 2024) e todas as 4 áreas (CN, CH, LC, MT)
python main.py
```

### Execuções com Filtros Opcionais
Se desejar focar em um ano ou área específicos, basta passar os argumentos:

```bash
# Executar apenas um ano específico (todas as áreas daquele ano)
python main.py --year 2024

# Executar apenas uma área específica (todos os anos de Matemática)
python main.py --area MT

# Executar ano e área específicos
python main.py --year 2024 --area MT

# Executar múltiplas áreas ou intervalo de anos
python main.py --area CN,MT --year 2020-2024

# Apenas organizar e desaninhar pastas em raw/ sem executar a extração
python main.py --organize
```

---

## 📂 Estrutura do Repositório

```text
microdados-enem-item-enriquecido/
│
├── raw/                                  # Dados brutos dos microdados (descompactados)
│   ├── microdados_enem_2009/
│   │   ├── DADOS/ITENS_PROVA_2009.csv
│   │   ├── DICIONÁRIO/...
│   │   └── PROVAS E GABARITOS/*.pdf
│   └── ...
│
├── processed/                            # Datasets finais enriquecidos
│   ├── itens_prova_{ANO}_enriquecido.csv      # Base anual com as áreas processadas
│   └── itens_prova_2009_2024_enriquecido.csv  # Base consolidada multi-ano unificada
│
├── src/
│   ├── __init__.py
│   ├── config.py                         # Constantes (áreas, mapeamento de dias, cores)
│   ├── catalog.py                        # Catálogo canônico de referência de PDFs oficiais
│   ├── pdf_fingerprint.py                # Leitor dinâmico de folha de rosto (PyMuPDF: Dia 1/2, Cor, P1/P2)
│   ├── pdf_matcher.py                    # Seleção unária e casamento dinâmico multi-área
│   ├── organize.py                       # Desaninhamento e padronização automática de pastas
│   ├── pdf_extractor.py                  # Extração textual, alternativas A-E e imagens
│   ├── pipeline.py                       # Orquestrador com cache compartilhado de cadernos
│   └── dictionary_parser.py              # Leitor dinâmico de códigos de prova no Excel
│
├── main.py                               # Ponto de entrada CLI simplificado
├── requirements.txt                      # Dependências Python (pandas, openpyxl, pymupdf)
├── AGENTS.md                             # Contexto arquitetural e regras para agentes de IA
└── README.md                             # Este guia
```

---

## 🛠️ Como Reproduzir a Base

### 1. Preparar o Ambiente

```bash
git clone https://github.com/SEU_USUARIO/microdados-enem-item-enriquecido.git
cd microdados-enem-item-enriquecido

python -m venv .venv

# Linux / WSL / macOS:
source .venv/bin/activate

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

---

### 2. Obter os Dados Brutos do INEP

Baixe os pacotes compactados de microdados das edições desejadas no portal oficial do INEP:
- **Página de Microdados do INEP**: [gov.br/inep - Microdados do Enem](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem)

Descompacte cada arquivo `.zip` dentro da pasta `raw/`, seguindo o padrão `raw/microdados_enem_{ANO}`:
```text
raw/
├── microdados_enem_2009/
├── microdados_enem_2010/
...
└── microdados_enem_2024/
```

> **Pastas aninhadas e extensões duplas:** Caso a descompactação gere pastas repetidas (como `microdados_enem_2023/microdados_enem_2023/`) ou arquivos com `.pdf.pdf` (como em 2015), o sistema desaninhará e corrigirá tudo automaticamente.

---

### 3. Cadernos Complementares de Reaplicação / PPL (2012, 2013 e 2014)

Nos pacotes de microdados oficiais de **2012, 2013 e 2014**, o INEP incluiu na pasta `PROVAS E GABARITOS` apenas os cadernos da 1ª aplicação regular, omitindo os cadernos da 2ª aplicação (PPL), embora os dados psicométricos dos itens estejam presentes no CSV `ITENS_PROVA_{ANO}.csv`.

Caso deseje incluir as questões de PPL desses 3 anos para compor o banco completo:

1. Acesse o repositório oficial de provas anteriores:
   - [Portal Gov.br - INEP: Provas e Gabaritos do Enem](https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem/provas-e-gabaritos)
2. Selecione a seção **Reaplicação / PPL** e baixe o caderno desejado:
   - **2012**: 2º Dia — Caderno 6 (Cinza) — Reaplicação / PPL
   - **2013**: 2º Dia — Caderno 6 (Cinza) — Reaplicação / PPL
   - **2014**: 2º Dia — Caderno 6 (Cinza) — Reaplicação / PPL
3. Salve cada PDF dentro da pasta correspondente:
   - `raw/microdados_enem_2012/PROVAS E GABARITOS/`
   - `raw/microdados_enem_2013/PROVAS e GABARITOS/`
   - `raw/microdados_enem_2014/PROVAS e GABARITOS/`

> **Mapeamento e Renomeação Automáticos:** Você pode salvar esses arquivos com **qualquer nome**. O módulo `src/pdf_fingerprint.py` inspeciona a folha de rosto via PyMuPDF, detecta a indicação `"2ª APLICAÇÃO"`, identifica o dia e a cor, e realiza o casamento com o código de prova do INEP, sem necessidade de renomeação manual.

---

## 📊 Especificação das Colunas do Dataset

O dataset gerado em `processed/` utiliza codificação `utf-8-sig` (UTF-8 com BOM) e delimitador `;`.

### Colunas Oficiais Preservadas do INEP:
| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `CO_POSICAO` | `int` | Posição física da questão no caderno (1 a 180). |
| `SG_AREA` | `str` | Sigla da área do conhecimento (`CN`, `CH`, `LC` ou `MT`). |
| `CO_ITEM` | `int` | Código identificador universal único do item no banco do INEP. |
| `TX_GABARITO` | `str` | Alternativa correta oficial (`A`, `B`, `C`, `D`, `E` ou `*` se questão anulada). |
| `CO_HABILIDADE`| `int` | Código da habilidade avaliada na Matriz de Referência do ENEM. |
| `IN_ITEM_ABAN` | `int` | Indicador de item abandonado no pré-teste / calibração. |
| `TX_MOTIVO_ABAN`| `str` | Justificativa do abandono do item, quando aplicável. |
| `NU_PARAM_A` | `float`| **Parâmetro $a$ da TRI**: Discriminação do item. |
| `NU_PARAM_B` | `float`| **Parâmetro $b$ da TRI**: Dificuldade do item. |
| `NU_PARAM_C` | `float`| **Parâmetro $c$ da TRI**: Acerto casual / adivinhação. |
| `TX_COR` | `str` | Cor do caderno selecionado (ex: `AMARELO`, `AZUL`, `CINZA`). |
| `CO_PROVA` | `int` | Código numérico da prova no sistema do INEP. |
| `TP_LINGUA` | `float`| Indicador de língua estrangeira (`0` para Inglês, `1` para Espanhol, `NaN` para itens gerais). |
| `IN_ITEM_ADAPTADO`| `int` | Indicador de adaptação especial (sempre `0` ou `NaN` neste escopo). |

### Colunas Enriquecidas Geradas:
| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `ANO_APLICACAO` | `int` | Ano da edição do ENEM (2009 a 2024). |
| `TP_APLICACAO` | `str` | Classificação da aplicação: `REGULAR` (1ª aplicação) ou `REAPLICACAO_PPL` (2ª aplicação). |
| `REF_ARQUIVO_PDF` | `str` | Nome exato do arquivo PDF de onde o item foi extraído. |
| `DESC_ENUNCIADO`| `str` | Texto integral limpo e sanitizado do enunciado da questão. |
| `DESC_ALTER_A` | `str` | Texto integral da alternativa A. |
| `DESC_ALTER_B` | `str` | Texto integral da alternativa B. |
| `DESC_ALTER_C` | `str` | Texto integral da alternativa C. |
| `DESC_ALTER_D` | `str` | Texto integral da alternativa D. |
| `DESC_ALTER_E` | `str` | Texto integral da alternativa E. |
| `IN_ITEM_IMAGEM`| `int` | Indicador binário: `1` se há imagem, figura ou gráfico no item; `0` se é puramente textual. |

> **Nota sobre Alternativas Gráficas:** Alternativas cujo conteúdo é estritamente visual (figura geométrica, mapa, charge ou diagrama sem texto legível) recebem a marcação padronizada `[Figura / Imagem]`.
