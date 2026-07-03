# Фабрика гипотез (Hypothesis Factory)

Система генерации и ранжирования проверяемых гипотез по кейсам Норникеля: ETL → граф знаний → RAG → Yandex GPT → scoring.

## Быстрый старт (для жюри)

```bash
git clone https://github.com/Selest6/hypothesis-factory.git
cd hypothesis-factory
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # вписать YANDEX_API_KEY и YANDEX_FOLDER_ID
python scripts/test_pipeline.py --case-id nof_med --mode demo
```

`data/processed/` и `data/chroma/` уже в репозитории — **пересборка не нужна** для демо.

## Полная пересборка с нуля

1. Скачать данные: [Яндекс.Диск](https://disk.yandex.ru/d/qE55fooRQGNVVA) → распаковать в `data/raw/` (см. `data/raw/README.md`)

2. ETL + граф + индекс:

```bash
python scripts/ingest_all.py --data-dir data/raw
python scripts/build_graph.py --all-cases
python scripts/build_index.py --reset
```

3. Генерация гипотез:

```bash
python scripts/test_pipeline.py --case-id nof_med
```

## Структура

| Путь | Назначение |
|------|------------|
| `src/etl/` | Парсеры Excel, PDF, docx |
| `src/graph/` | NetworkX граф + scoring |
| `src/rag/` | ChromaDB + keyword retrieval |
| `src/llm/` | Yandex GPT, промпты, pipeline |
| `data/processed/` | triplets, chunks, embeddings, graph summaries |
| `data/chroma/` | готовый векторный индекс |
| `data/cache/` | кэш demo-прогонов (4 кейса, без API) |

## Demo / Live

```bash
# Demo — без API, из data/cache/
python scripts/test_pipeline.py --case-id nof_med --mode demo
python scripts/test_pipeline.py --all-cases --mode demo

# Live — Yandex GPT (нужен .env)
python scripts/test_pipeline.py --case-id nof_med --mode live

# Пересобрать cache (offline, если квота API исчерпана)
python scripts/build_cache.py --mode offline

# Экспорт JSON + Markdown
python scripts/export_results.py --mode cache
```

## API-ключи

Создайте `.env` из `.env.example`:

```
YANDEX_API_KEY=...
YANDEX_FOLDER_ID=...
```

Ключи **не коммитить** в git.

## Кейсы

| case_id | Название |
|---------|----------|
| `kgmk` | КГМК |
| `nof_med` | НОФ мед |
| `nof_vkr` | НОФ вкр |
| `tof` | ТОФ |

## Pipeline из кода

```python
from src.llm.pipeline import run_pipeline

result = run_pipeline("nof_med", mode="live")
for h in result.hypotheses:
    print(h.title, h.scores.total)
```
