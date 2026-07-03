"""Human-readable labels for KPI diagnostics (no heavy imports)."""

from __future__ import annotations

CONTEXT_LABELS: dict[str, str] = {
    "tailings_summary": "Сводка по отвальным хвостам",
    "feed": "Питание фабрики (вход)",
    "tailings": "Детализация внутри хвостов",
}

CONTEXT_HINTS: dict[str, str] = {
    "tailings_summary": "Общая строка «Отвальные хвосты» — итог потерь по всему разделу хвостов.",
    "feed": "Материал на входе в переработку, не хвосты.",
    "tailings": "Строка внутри таблицы хвостов (по минералу или классу).",
}

SUBJECT_HINTS: dict[str, str] = {
    "Отвальные хвосты": "Отходы обогащения, которые уходят на отвал.",
    "Итого извлекаемый металл": "Итоговая строка Excel: сумма по минералам, из которых металл ещё можно доизвлечь.",
    "Итого не извлекаемый металл": "Итоговая строка Excel: металл в форме, из которой извлечение практически невозможно.",
}


def format_context_label(context: str | None) -> str:
    if not context:
        return "—"
    if context in CONTEXT_LABELS:
        return CONTEXT_LABELS[context]
    if "мкм" in context or context.startswith("-"):
        return f"Класс крупности {context}"
    return context


def format_context_hint(context: str | None) -> str | None:
    if not context:
        return None
    if context in CONTEXT_HINTS:
        return CONTEXT_HINTS[context]
    if "мкм" in context or context.startswith("-"):
        return f"Фракция руды/хвостов с крупностью {context} — одна из строк таблицы по ситам."
    return None


def format_subject_hint(subject: str) -> str | None:
    for key, hint in SUBJECT_HINTS.items():
        if key.lower() in subject.lower():
            return hint
    if subject.lower().startswith("итого"):
        return "Итоговая (суммарная) строка в таблице Excel."
    return None
