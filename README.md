# Base Enriquecida de Itens do ENEM (Matemática — 2009 a 2024)

Pipeline de dados automatizada para unir os microdados tabulares psicométricos oficiais do INEP com o conteúdo textual e gráfico dos cadernos de prova em formato PDF, com foco na área de **Matemática e suas Tecnologias (`SG_AREA = 'MT'`)**.

O resultado final é uma base consolidada com **1.395 itens calibrados pela TRI (Teoria de Resposta ao Item)**, contendo enunciados limpos, alternativas separadas (A a E), parâmetros psicométricos oficiais e indicador de presença de figuras/gráficos.

---

## 🎯 Metodologia e Escopo

Cada edição do ENEM aplica 4 cores de cadernos regulares (ex: Azul, Amarelo, Branco, Rosa, Cinza) que contêm **as mesmas 45 questões** em ordens distintas. Além disso, a partir de 2010, o INEP realiza uma segunda aplicação (Reaplicação / PPL — Pessoas Privadas de Liberdade) com **45 questões inéditas**.

Para maximizar a diversidade de itens e eliminar redundâncias, este projeto adota uma **amostragem unária representativa por aplicação**:

1. **1 Cor da Prova Regular (1ª Aplicação — P1)**: 45 questões únicas por edição.
2. **1 Cor da Prova de Reaplicação / PPL (2ª Aplicação — P2)**: 45 questões inéditas por edição (de 2010 a 2024).
3. **Exclusão Estrita de Provas Adaptadas e Digitais**: São excluídos cadernos adaptados (Ledor, Braile, Libras, Ampliada, Superampliada, Leitor de Tela) e aplicações exclusivamente digitais (2020 a 2022).

### Volume Consolidado
- **2009**: 45 itens (apenas aplicação regular).
- **2010 a 2024 (15 edições)**: 90 itens por ano (45 Regular + 45 PPL).
- **Total na base consolidada**: **1.395 itens únicos**.

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
│   ├── itens_prova_{ANO}_enriquecido.csv      # Bases anuais individuais
│   └── itens_prova_2009_2024_enriquecido.csv  # Base consolidada multi-ano (1.395 itens)
│
├── src/
│   ├── __init__.py
│   ├── config.py                         # Constantes (MT, Dia 2), cores e filtros de adaptação
│   ├── catalog.py                        # Catálogo canônico de referência de PDFs oficiais
│   ├── pdf_fingerprint.py                # Leitor inteligente de folha de rosto (PyMuPDF)
│   ├── pdf_matcher.py                    # Seleção unária e casamento dinâmico (P1 e P2)
│   ├── organize.py                       # Desaninhamento e padronização automática de arquivos
│   ├── pdf_extractor.py                  # Extração textual, alternativas A-E e imagens
│   ├── pipeline.py                       # Orquestrador da pipeline de ponta a ponta
│   └── dictionary_parser.py              # Leitor dinâmico do dicionário de dados em Excel
│
├── main.py                               # Ponto de entrada CLI
├── requirements.txt                      # Dependências Python (pandas, openpyxl, pymupdf)
├── AGENTS.md                             # Contexto arquitetural e regras para agentes de IA
└── README.md                             # Este guia
```

---

## 🛠️ Como Reproduzir a Base

### 1. Preparar o Ambiente

Clone o repositório e ative um ambiente virtual Python (3.10 a 3.12 recomendado):

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

Baixe os pacotes compactados de microdados das edições desejadas (ou de todas de 2009 a 2024) no portal oficial de Dados Abertos do INEP:
- **Página de Microdados do INEP**: [gov.br/inep - Microdados do Enem](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem)

Descompacte cada arquivo `.zip` dentro da pasta `raw/`, seguindo o padrão `raw/microdados_enem_{ANO}`:
```text
raw/
├── microdados_enem_2009/
├── microdados_enem_2010/
...
└── microdados_enem_2024/
```

> **Nota sobre pastas aninhadas:** Caso a descompactação gere pastas repetidas (como `microdados_enem_2023/microdados_enem_2023/`), o sistema desaninhará e organizará tudo de forma automática.

---

### 3. Cadernos Complementares de Reaplicação / PPL (2012, 2013 e 2014)

Nos pacotes de microdados oficiais de **2012, 2013 e 2014**, o INEP incluiu na pasta `PROVAS E GABARITOS` apenas os cadernos da 1ª aplicação regular, omitindo os cadernos da 2ª aplicação (PPL), embora os dados psicométricos dos itens estejam presentes no CSV `ITENS_PROVA_{ANO}.csv`.

Caso deseje incluir as 45 questões de PPL desses 3 anos para compor o banco completo de 1.395 itens:

1. Acesse o repositório oficial de provas anteriores:
   - [Portal Gov.br - INEP: Provas e Gabaritos do Enem](https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem/provas-e-gabaritos)
2. Selecione a seção **Reaplicação / PPL** e baixe o caderno do **2º Dia (Cinza)**:
   - **2012**: 2º Dia — Caderno 6 (Cinza) — Reaplicação / PPL
   - **2013**: 2º Dia — Caderno 6 (Cinza) — Reaplicação / PPL
   - **2014**: 2º Dia — Caderno 6 (Cinza) — Reaplicação / PPL
3. Salve cada PDF dentro da pasta correspondente:
   - `raw/microdados_enem_2012/PROVAS E GABARITOS/`
   - `raw/microdados_enem_2013/PROVAS e GABARITOS/`
   - `raw/microdados_enem_2014/PROVAS e GABARITOS/`

> **Mapeamento e Renomeação 100% Automáticos:** Você pode salvar esses arquivos com **qualquer nome** (ex: `caderno_ppl.pdf` ou o nome original do download). O módulo `src/pdf_fingerprint.py` inspeciona a folha de rosto do documento via PyMuPDF, detecta a indicação `"2ª APLICAÇÃO"`, identifica o dia e a cor, e realiza o casamento exato com o código de prova do INEP, sem necessidade de renomeação manual.

---

### 4. Executar a Pipeline

Você pode executar para uma única edição ou para todo o histórico:

```bash
# Opcional: normaliza pastas aninhadas, extensões e nomes em raw/
python main.py --organize

# Executar apenas uma edição específica (ex: 2024)
python main.py --year 2024

# Executar um intervalo de edições (ex: 2020 a 2024)
python main.py --year 2020-2024

# Executar todas as 16 edições (2009 a 2024) e consolidar os dados automaticamente
python main.py -all
```

---

## 📊 Especificação das Colunas do Dataset

O dataset gerado em `processed/` (tanto os anuais quanto o consolidado `itens_prova_2009_2024_enriquecido.csv`) utiliza codificação `utf-8-sig` (UTF-8 com BOM) e delimitador `;`.

### Colunas Oficiais Preservadas do INEP:
| Coluna | Tipo | Descrição |
| :--- | :--- | :--- |
| `CO_POSICAO` | `int` | Posição física da questão no caderno (1 a 45 ou 136 a 180). |
| `SG_AREA` | `str` | Área do conhecimento (`MT` para Matemática). |
| `CO_ITEM` | `int` | Código identificador universal único do item no banco do INEP. |
| `TX_GABARITO` | `str` | Alternativa correta oficial (`A`, `B`, `C`, `D`, `E` ou `*` se questão anulada). |
| `CO_HABILIDADE`| `int` | Código da habilidade avaliada (Matriz de Referência de Matemática do ENEM). |
| `IN_ITEM_ABAN` | `int` | Indicador de item abandonado no pré-teste / calibração. |
| `TX_MOTIVO_ABAN`| `str` | Justificativa do abandono do item, quando aplicável. |
| `NU_PARAM_A` | `float`| **Parâmetro $a$ da TRI**: Discriminação do item (capacidade de diferenciar participantes com proficiências distintas). |
| `NU_PARAM_B` | `float`| **Parâmetro $b$ da TRI**: Dificuldade do item (ponto na escala de proficiência onde a probabilidade de acerto é mediana). |
| `NU_PARAM_C` | `float`| **Parâmetro $c$ da TRI**: Acerto casual / adivinhação (probabilidade de acerto por participante com proficiência infinitamente baixa). |
| `TX_COR` | `str` | Cor do caderno selecionado (ex: `AMARELO`, `AZUL`, `CINZA`). |
| `CO_PROVA` | `int` | Código numérico da prova no sistema do INEP. |
| `TP_LINGUA` | `float`| Indicador de língua estrangeira (quando aplicável no dia). |
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
| `IN_ITEM_IMAGEM`| `int` | Indicador binário: `1` se há imagem, figura geométrica ou gráfico no item; `0` se é puramente textual. |

> **Nota sobre Alternativas Gráficas:** Alternativas cujo conteúdo é estritamente visual (figura geométrica, gráfico ou diagrama sem texto legível) recebem a marcação padronizada `[Figura / Imagem]`.

---

## 🔬 Rigor e Detalhes de Implementação

- **Inspeção de Layout de Duas Colunas**: A mancha gráfica dos cadernos de prova é dividida verticalmente pelo meio da página (`mid_x = page.rect.width / 2.0`), garantindo a ordem natural de leitura das questões.
- **Detecção Espacial de Imagens**: Identifica elementos visuais tanto via fluxos de imagem raster (*bitmaps*) quanto via vetores gráficos renderizados diretamente na página.
- **Reparo de CMaps de Fontes**: Para edições antigas cujos PDFs não incluíam tabelas `ToUnicode`, a pipeline reconstrói dinamicamente CMaps para símbolos matemáticos e fontes Type1.
- **Reconciliação de Omissões Oficiais**: Corrige omissões documentadas nas planilhas de dicionário do INEP (como a prova PPL código 136 de 2011, código 156 de 2012 e código 186 de 2013).
