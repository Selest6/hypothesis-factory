# Фабрика гипотез (Hypothesis Factory)

Система генерации и ранжирования проверяемых гипотез по кейсам Норникеля: ETL → граф знаний → RAG → Yandex GPT → scoring → Streamlit UI.

## Попробуйте онлайн

Развёрнутая версия «Фабрики гипотез» доступна в браузере — можно выбрать кейс, задать KPI, сгенерировать гипотезы, посмотреть граф связей и скачать отчёт. Ничего устанавливать не нужно:

**https://hypothesis-factory-ejdz2fke2mtjkep6dzdgyt.streamlit.app/**

**Подсказка:** выберите кейс в боковой панели → нажмите «Сгенерировать гипотезы» → изучите карточки и экспорт в PDF/DOCX.

## Локальный запуск (macOS и Windows)

Общие шаги: клонировать репозиторий, установить зависимости, указать ключи Yandex GPT в `.env`, запустить Streamlit.

`data/processed/` уже в репозитории — **пересборка данных не нужна** только чтобы открыть UI.

Откройте в браузере **http://localhost:8501** → выберите кейс → «Сгенерировать гипотезы».

Без `YANDEX_API_KEY` и `YANDEX_FOLDER_ID` интерфейс откроется, но генерация гипотез не заработает.

```bash
git clone https://github.com/Selest6/hypothesis-factory.git
cd hypothesis-factory

python3 -m venv .venv              # macOS
# python -m venv .venv             # Windows

source .venv/bin/activate          # macOS
# .venv\Scripts\activate           # Windows

pip install -r requirements.txt

cp .env.example .env               # macOS
# copy .env.example .env           # Windows
# отредактируйте .env: YANDEX_API_KEY, YANDEX_FOLDER_ID

streamlit run app.py
```

## Ссылки

| | |
|---|---|
| **Код** | [GitHub — Selest6/hypothesis-factory](https://github.com/Selest6/hypothesis-factory) |
| **Презентация, видео и описание** | [Яндекс.Диск](https://disk.360.yandex.ru/d/fGI0FNZxqgxD8w) |
| **Исходные данные организаторов** | [Яндекс.Диск](https://disk.yandex.ru/d/qE55fooRQGNVVA) (Excel, PDF, docx кейсов) |

## Streamlit UI

| Экран | Что показывает |
|-------|----------------|
| **Шаг 1 — Generate** | Генерация через Yandex GPT |
| **Шаг 2 — Карточки** | Scores + novelty vs литература + источники + верификация |
| **Граф связей** | 15–22 узла вокруг KPI-узла (pyvis, по чекбоксу) |
| **Экспорт** | Markdown / JSON / CSV / PDF / DOCX |

## Yandex GPT

Проверка API перед запуском UI (после настройки `.env` — см. выше):

```bash
python scripts/test_pipeline.py --case-id nof_med
streamlit run app.py
```

## Docker

```bash
docker compose up --build
```

## Полная пересборка данных

1. Скачать данные организаторов: [Яндекс.Диск](https://disk.yandex.ru/d/qE55fooRQGNVVA) → `data/raw/`
2. ETL + граф + индекс:

```bash
python scripts/ingest_all.py --data-dir data/raw
python scripts/ingest_ocr.py --data-dir data/raw    # схемы PNG + PDF без текста → OCR
python scripts/build_graph.py --all-cases
python scripts/build_embeddings.py --reset
python scripts/build_index.py --reset
python scripts/ocr_progress.py                    # прогресс OCR (опционально)
```

## Структура

| Путь | Назначение |
|------|------------|
| `app.py` | Streamlit UI |
| `src/ui/` | Mini-graph, экспорт, стили |
| `src/etl/` | Парсеры Excel, PDF, docx, Yandex Vision OCR |
| `src/graph/` | NetworkX граф + scoring |
| `src/rag/` | ChromaDB + keyword retrieval |
| `src/llm/` | Yandex GPT, промпты, pipeline |
| `data/processed/` | triplets, chunks, graph summaries |

## Кейсы

| case_id | Название |
|---------|----------|
| `all` | Все фабрики (объединённый контекст) |
| `kgmk` | КГМК |
| `nof_med` | НОФ мед |
| `nof_vkr` | НОФ вкр |
| `tof` | ТОФ |

## Pipeline из кода

```python
from src.llm.pipeline import run_pipeline

result = run_pipeline("nof_med")
for h in result.hypotheses:
    print(h.title, h.scores.total if h.scores else "")
```
