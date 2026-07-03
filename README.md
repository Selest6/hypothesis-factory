# Hypothesis Factory

Инструмент генерации и ранжирования гипотез для НИИ (кейс Норникель / обогащение).

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# заполните YANDEX_API_KEY и YANDEX_FOLDER_ID
```

## Данные

```bash
# ETL: Excel / PDF / docx → JSON
python scripts/ingest_all.py --data-dir /path/to/dataset

# Embeddings через Yandex API (с checkpoint, ~20–30 мин)
python scripts/build_embeddings.py
```

Результат: `data/processed/embeddings.json` (3076 документов, dim=256).

## Структура

```
scripts/ingest_all.py       — парсинг датасета
scripts/build_embeddings.py — Yandex embeddings + checkpoint
src/rag/embeddings.py       — клиент Yandex Embeddings API
src/etl/                    — парсеры Excel, PDF, docx
data/processed/             — triplets, chunks, embeddings
```

## Секреты

Файл `.env` не коммитится. Используйте `.env.example` как шаблон.
