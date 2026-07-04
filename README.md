# Фабрика гипотез (Hypothesis Factory)

Система генерации и ранжирования проверяемых гипотез по кейсам Норникеля: ETL → граф знаний → RAG → Yandex GPT → scoring → Streamlit UI.

## Быстрый старт

```bash
git clone https://github.com/Selest6/hypothesis-factory.git
cd hypothesis-factory
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # YANDEX_API_KEY, YANDEX_FOLDER_ID
streamlit run app.py
```

Откройте http://localhost:8501 → выберите кейс → «Сгенерировать гипотезы».

`data/processed/` уже в репозитории — **пересборка не нужна** для запуска UI.

## Streamlit UI

| Экран | Что показывает |
|-------|----------------|
| **Шаг 1 — Generate** | Генерация через Yandex GPT |
| **Шаг 2 — Карточки** | Scores + novelty vs литература + источники + верификация |
| **Граф связей** | 15–22 узла вокруг KPI-узла (pyvis, по чекбоксу) |
| **Экспорт** | Markdown / JSON / CSV / PDF / DOCX |

## Yandex GPT

```bash
copy .env.example .env   # YANDEX_API_KEY, YANDEX_FOLDER_ID
python scripts/test_pipeline.py --case-id nof_med
streamlit run app.py
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
