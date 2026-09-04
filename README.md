# Pipeline de Extração e Enriquecimento de Itens do ENEM

Pipeline em Python para correlacionar os dados estruturados de `ITENS_PROVA_{ANO}.csv` com os enunciados e alternativas contidos nos cadernos de prova em formato PDF, adicionando metadados de texto, arquivo de origem e presença de imagens.

---

## 📌 Estrutura do Projeto

```text
microdados_enem/
│
├── .venv/                         # Ambiente virtual Python
├── raw/                           # Dados brutos dos microdados (INEP)
│   ├── microdados_enem_2020.zip
│   ├── microdados_enem_2021.zip
│   ├── microdados_enem_2022.zip
│   ├── microdados_enem_2023.zip
│   └── microdados_enem_2024/
│       ├── DADOS/ITENS_PROVA_2024.csv
│       ├── DICIONÁRIO/Dicionário_Microdados_Enem_2024.xlsx
│       └── PROVAS E GABARITOS/*.pdf
│
├── src/
│   ├── __init__.py
│   ├── config.py                  # Mapeamentos de áreas, dias, cores e regex
│   ├── dictionary_parser.py       # Leitor do dicionário Excel para obter códigos de prova
│   ├── pdf_matcher.py             # Resolução dinâmica dos arquivos PDF por área/cor
│   ├── pdf_extractor.py           # Extração de enunciados, alternativas e detecção de imagem
│   └── pipeline.py                # Orquestrador da execução e geração do dataset final
│
├── processed/
│   └── itens_prova_2024_enriquecido.csv  # Base final enriquecida
│
├── requirements.txt               # Dependências do projeto
├── main.py                        # Ponto de entrada CLI
└── README.md
```

---

## 🚀 Como Executar

### 1. Ativar o Ambiente Virtual
No Windows PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Executar a Pipeline para 2024
```powershell
python main.py --year 2024
```

Ou especificando o executável do venv diretamente:
```powershell
.\.venv\Scripts\python.exe main.py --year 2024
```

---

## 📊 Novas Colunas Adicionadas

Além das colunas originais do INEP (`CO_POSICAO`, `SG_AREA`, `CO_ITEM`, `TX_GABARITO`, `CO_HABILIDADE`, `TX_COR`, `CO_PROVA`, `TP_LINGUA`, etc.), foram adicionadas:

| Coluna | Tipo | Descrição | Exemplo |
| :--- | :--- | :--- | :--- |
| `REF_ARQUIVO_PDF` | `str` | Nome do arquivo PDF do caderno de prova de onde os dados foram extraídos | `ENEM_2024_P1_CAD_07_DIA_2_AZUL.pdf` |
| `DESC_ENUNCIADO` | `str` | Texto completo do enunciado da questão limpo | `"Muitas pessoas ainda se espantam..."` |
| `DESC_ALTER_A` | `str` | Texto da alternativa A | `"aciona os airbags do veículo."` |
| `DESC_ALTER_B` | `str` | Texto da alternativa B | `"absorve a energia cinética do sistema."` |
| `DESC_ALTER_C` | `str` | Texto da alternativa C | `"consome a quantidade de movimento do sistema."` |
| `DESC_ALTER_D` | `str` | Texto da alternativa D | `"cria uma barreira de proteção..."` |
| `DESC_ALTER_E` | `str` | Texto da alternativa E | `"diminui a velocidade do centro..."` |
| `IN_ITEM_IMAGEM` | `int` | Indicador binário (`1` se a questão contém imagem no enunciado/alternativas, `0` caso contrário) | `1` ou `0` |

> **Nota:** Alternativas cujo conteúdo é estritamente gráfico (ex: diagramas de circuitos elétricos, gráficos, heredogramas) são identificadas como `[Figura / Imagem]`.

---

## 📈 Resultados da Validação (2024)

- **Total de Itens Regulares Processados**: 740 de 740 (100.0%)
- **Cadernos Mapeados**: 8 cadernos de prova regulares (Dia 1: Azul, Amarelo, Branco, Verde; Dia 2: Amarelo, Cinza, Azul, Verde)
- **Completude de Dados**: 0 valores vazios ou nulos em todas as colunas enriquecidas
- **Itens com Imagem Detectada**: 228 de 740 (30.8%)
- **Formato de Saída**: CSV UTF-8 com BOM (`utf-8-sig`) separado por `;`, compatível nativamente com Excel e bibliotecas de Data Science.
