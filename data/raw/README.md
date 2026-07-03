# Исходные данные организаторов

Скачайте архив с [Яндекс.Диска](https://disk.yandex.ru/d/qE55fooRQGNVVA) и распакуйте содержимое **сюда** (`data/raw/`).

Ожидаемая структура:

```
data/raw/
  пример 1/   … Excel, docx
  пример 2/
  пример 3/
  пример 4/
  … PDF-учебники
```

После распаковки пересоберите processed-артефакты:

```bash
python scripts/ingest_all.py --data-dir data/raw
python scripts/build_graph.py --all-cases
python scripts/build_index.py --reset
```

В репозитории уже лежит готовый `data/processed/` — для демо жюри пересборка **не обязательна**.
