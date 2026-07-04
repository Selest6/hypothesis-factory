# Оригинальные документы для скачивания из UI

Кнопка **⬇** у источника в карточке гипотезы отдаёт файл из этой папки.

## Автозагрузка с Яндекс.Диска организаторов

```bash
python scripts/download_yandex_disk_sources.py
```

Источник: https://disk.yandex.ru/d/qE55fooRQGNVVA

## Вручную (если уже скачали архив)

```bash
python scripts/collect_sources.py --data-dir data/raw
```

После загрузки закоммитьте `data/sources/` — тогда кнопки работают и на Streamlit Cloud.
