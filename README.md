# Фабрика гипотез (Hypothesis Factory)

Система генерации и ранжирования проверяемых гипотез по кейсам Норникеля: ETL → граф знаний → RAG → Yandex GPT → scoring → Streamlit UI. На выходе — **top-5** проверяемых гипотез с источниками, интерпретируемыми оценками и экспортом отчёта.

## Попробуйте онлайн

Развёрнутая версия «Фабрики гипотез» доступна в браузере — можно выбрать кейс, задать KPI, сгенерировать гипотезы, посмотреть граф связей и скачать отчёт. Ничего устанавливать не нужно:

**https://hypothesis-factory-ejdz2fke2mtjkep6dzdgyt.streamlit.app/**

**Подсказка:** выберите кейс в боковой панели → нажмите «Сгенерировать гипотезы» (≈2–3 мин) → изучите карточки и экспорт в PDF/DOCX.

## Локальный запуск (macOS и Windows)

Требуется **Python 3.10+**. Клонировать репозиторий, установить зависимости, указать ключи Yandex GPT в `.env`, запустить Streamlit.

Готовые данные и индекс — см. раздел [Данные в репозитории](#данные-в-репозитории); **пересборка не нужна** только чтобы открыть UI.

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

## Возможности

| Функция | Описание |
|---------|----------|
| **Кейс и KPI** | Выбор фабрики (или «все кейсы»), редактирование KPI-цели и ограничений в sidebar |
| **Генерация** | Yandex GPT синтезирует гипотезы из Excel, графа, литературы и OCR-схем |
| **Ранжирование top-5** | Баллы: новизна, обоснованность (источники), ценность для KPI, риск |
| **Экспертные веса** | Ползунки в «Настроить веса» — меняют приоритет критериев ранжирования |
| **Новизна** | Сравнение с prior art из базы; пояснение «своя идея» / «похоже на известное» |
| **Источники** | Ссылки на файл, лист/строку Excel, страницу PDF, OCR-схему; скачивание исходника |
| **Доработка** | «Переделать с учётом замечания» — уточнение одной гипотезы по фидбеку |
| **Полезные ссылки** | Опциональный чекбокс 🌐 — подборка проверенных ссылок для чтения (не в промпт GPT) |
| **Граф** | Фрагмент графа знаний вокруг KPI (pyvis) |
| **Экспорт** | Markdown, JSON, CSV, PDF, DOCX |

## Данные в репозитории

Для демо и локального UI **не нужно** скачивать архив организаторов и гонять ETL — всё уже подготовлено:

| Путь | Содержимое |
|------|------------|
| `data/processed/` | Triplets из Excel, chunks литературы и OCR, summaries графа |
| `data/chroma/` | Готовый векторный индекс ChromaDB для RAG |
| `data/sources/` | PDF и файлы для скачивания из UI (при необходимости — подгрузка с [Я.Диска организаторов](https://disk.yandex.ru/d/qE55fooRQGNVVA)) |

Полная пересборка с нуля — только если меняете исходные файлы (см. ниже).

## Деплой (Streamlit Cloud)

Онлайн-версия развёрнута на [Streamlit Cloud](https://hypothesis-factory-ejdz2fke2mtjkep6dzdgyt.streamlit.app/) из ветки `main`.

Ключи Yandex GPT задаются в **Settings → Secrets** приложения (не в репозитории):

```toml
YANDEX_API_KEY = "..."
YANDEX_FOLDER_ID = "..."
```

Локально те же переменные — в файле `.env` (см. `.env.example`).

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

Нужен `.env` с ключами Yandex GPT. Приложение на порту **8501**.

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
| `data/chroma/` | ChromaDB-индекс для RAG |
| `data/sources/` | Исходные PDF/файлы для UI |

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
