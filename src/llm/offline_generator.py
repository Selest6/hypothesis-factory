from __future__ import annotations

from typing import Any

from src.models.schemas import GeneratedHypothesis, SourceRef
from src.rag.context import RetrievalContext


def _source_from_row(row: dict[str, Any]) -> SourceRef:
    src = row.get("source") or {}
    return SourceRef(
        file=str(src.get("file") or "требует верификации"),
        sheet=src.get("sheet"),
        row=src.get("row"),
        page=src.get("page"),
        fragment=row.get("subject") or src.get("fragment"),
    )


def _source_from_chunk(chunk: dict[str, Any]) -> SourceRef:
    src = chunk.get("source") or chunk.get("metadata") or {}
    if isinstance(src, dict) and "source_file" in src:
        return SourceRef(
            file=str(src.get("source_file") or "требует верификации"),
            sheet=src.get("sheet"),
            row=src.get("row"),
            page=src.get("page"),
            fragment=(chunk.get("text") or "")[:120],
        )
    return SourceRef(
        file=str(src.get("file") or "требует верификации"),
        sheet=src.get("sheet"),
        row=src.get("row"),
        page=src.get("page"),
        fragment=(chunk.get("text") or "")[:120],
    )


def _loss_hypothesis(context: RetrievalContext, loss: dict[str, Any]) -> GeneratedHypothesis:
    subject = loss.get("subject") or "процесс"
    element = loss.get("element") or "металл"
    value = loss.get("value")
    unit = loss.get("unit") or ""
    ctx_label = loss.get("context") or "хвосты"
    value_part = f" ({value} {unit})" if value not in (None, "") else ""
    title = f"Снижение потерь {element} в {ctx_label}: контроль {subject}"
    return GeneratedHypothesis(
        title=title,
        full_statement=(
            f"Если скорректировать режим «{subject}» с учётом KPI «{context.kpi_goal}», "
            f"то снизятся потери {element} в {ctx_label}{value_part}, "
            f"потому что узел связан с максимальными потерями по данным Excel."
        ),
        mechanism=(
            f"Изменение параметров «{subject}» должно уменьшить выход {element} "
            f"в {ctx_label} без ухудшения качества концентрата."
        ),
        kpi_impact=f"Снижение потерь {element} в {ctx_label} (точный % требует пилотного замера).",
        verification_steps=[
            f"Сравнить содержание {element} в {ctx_label} до/после изменения «{subject}».",
            "Проверить стабильность показателей концентрата на 3–5 смен.",
        ],
        sources=[_source_from_row(loss)],
        risks=[
            "Возможное снижение производительности участка при агрессивной оптимизации.",
            "Недостаточность данных для количественной оценки без пилота.",
        ],
    )


def _chunk_hypothesis(context: RetrievalContext, chunk: dict[str, Any]) -> GeneratedHypothesis:
    text = (chunk.get("text") or "").strip()
    snippet = text[:160].replace("\n", " ")
    title = f"Применение практики из базы знаний: {snippet[:72]}..."
    return GeneratedHypothesis(
        title=title,
        full_statement=(
            f"Если внедрить подход из источника («{snippet}...»), "
            f"то улучшится достижение KPI «{context.kpi_goal}», "
            f"потому что литература/отчёт описывает успешный механизм снижения потерь."
        ),
        mechanism="Перенос описанного в источнике технологического решения на текущий контур фабрики.",
        kpi_impact="Ожидаемое снижение потерь металла в хвостах (количественно — после пилота).",
        verification_steps=[
            "Сопоставить условия источника с текущим режимом фабрики.",
            "Запустить ограниченный пилот и замерить содержание в хвостах.",
        ],
        sources=[_source_from_chunk(chunk)],
        risks=[
            "Условия источника могут не совпадать с текущей рудой/схемой.",
            "Требуется адаптация реагентов или оборудования.",
        ],
    )


def _reference_variant(context: RetrievalContext, ref: dict[str, Any]) -> GeneratedHypothesis:
    title = ref.get("title") or "Эталонная гипотеза"
    src = ref.get("source") or {}
    source = SourceRef(
        file=str(src.get("file") or "требует верификации"),
        sheet=src.get("sheet"),
        row=src.get("row"),
        page=src.get("page"),
        fragment=title,
    )
    return GeneratedHypothesis(
        title=f"{title} (адаптация под KPI)",
        full_statement=(
            f"Если реализовать «{title}» с фокусом на «{context.kpi_goal}», "
            f"то снизятся потери металла в хвостах, "
            f"потому что гипотеза уже сформулирована экспертами для данного кейса."
        ),
        mechanism="Адаптация эталонной гипотезы организаторов под текущие ограничения и KPI.",
        kpi_impact="Снижение потерь элемента 28 в хвостах (оценка после пилота).",
        verification_steps=[
            "Согласовать параметры внедрения с технологами участка.",
            "Провести A/B замеры содержания в хвостах.",
        ],
        sources=[source],
        risks=[
            "Близость к известной гипотезе снижает новизну.",
            "Экономическая целесообразность требует отдельного расчёта.",
        ],
    )


def generate_offline_hypotheses(
    context: RetrievalContext,
    *,
    n_hypotheses: int = 7,
) -> list[GeneratedHypothesis]:
    """Build demo hypotheses from retrieved context without calling LLM."""
    candidates: list[GeneratedHypothesis] = []

    for loss in context.top_losses[:4]:
        candidates.append(_loss_hypothesis(context, loss))

    for chunk in context.text_chunks[:3]:
        candidates.append(_chunk_hypothesis(context, chunk))

    refs = context.reference_hypothesis_details or []
    for ref in refs[:3]:
        candidates.append(_reference_variant(context, ref))

    if not candidates and context.reference_hypotheses:
        for title in context.reference_hypotheses[:n_hypotheses]:
            candidates.append(
                _reference_variant(context, {"title": title, "source": {"file": "эталон"}})
            )

    seen_titles: set[str] = set()
    unique: list[GeneratedHypothesis] = []
    for item in candidates:
        key = item.title.lower()
        if key in seen_titles:
            continue
        seen_titles.add(key)
        unique.append(item)
        if len(unique) >= n_hypotheses:
            break

    return unique[:n_hypotheses]
