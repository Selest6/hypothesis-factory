# Фабрика гипотез (Hypothesis Factory)

Система генерации и ранжирования проверяемых гипотез по кейсам Норникеля: ETL → граф знаний → RAG → Yandex GPT → scoring → Streamlit UI.

## Быстрый старт (для жюри)

```bash
git clone https://github.com/Selest6/hypothesis-factory.git
cd hypothesis-factory
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
python scripts/build_demo_cache.py --offline   # Demo-кэш без API
streamlit run app.py
```

Откройте http://localhost:8501 → выберите кейс → **Demo mode** → «Сгенерировать гипотезы».

`data/processed/` уже в репозитории — **пересборка не нужна** для демо.

## Streamlit UI

| Экран | Что показывает |
|-------|----------------|
| **Шаг 1 — Диагностика KPI** | Топ-3 потери из Excel-triplets (файл, строка) |
| **Mini-graph** | 15–22 узла вокруг KPI-узла (pyvis) |
| **Шаг 2 — Generate** | Live (Yandex GPT) или Demo (кэш) |
| **Шаг 3 — Карточки** | Scores + novelty vs литература + источники + верификация |
| **Экспорт** | Markdown / JSON |

### Demo-кэш

```bash
# Без API — из данных KPI (для жюри)
python scripts/build_demo_cache.py --offline

# С API — реальная генерация + сохранение кэша
python scripts/build_demo_cache.py
```

## Live-режим (Yandex GPT)

```bash
copy .env.example .env   # YANDEX_API_KEY, YANDEX_FOLDER_ID
python scripts/test_pipeline.py --case-id nof_med
streamlit run app.py     # переключить режим на Live
```

## Docker

```bash
docker compose up --build
```

## Полная пересборка данных

1. Скачать данные: [Яндекс.Диск](https://disk.yandex.ru/d/qE55fooRQGNVVA) → `data/raw/`
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
| `src/ui/` | Диагностика KPI, mini-graph, экспорт, стили |
| `src/etl/` | Парсеры Excel, PDF, docx, Yandex Vision OCR |
| `src/graph/` | NetworkX граф + scoring |
| `src/rag/` | ChromaDB + keyword retrieval |
| `src/llm/` | Yandex GPT, промпты, pipeline |
| `data/processed/` | triplets, chunks, graph summaries |
| `data/cache/` | Demo-кэш прогонов |

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

result = run_pipeline("nof_med", mode="demo")
for h in result.hypotheses:
    print(h.title, h.scores.total if h.scores else "")
```
