from __future__ import annotations

SYSTEM_PROMPT = """\
Ты — инженер-технолог обогатительной фабрики Норильского никеля.
Твоя задача — предложить проверяемые гипотезы по снижению потерь металлов в хвостах.
Используй ТОЛЬКО факты из предоставленного контекста. Не выдумывай цифры.
Если данных недостаточно, укажи это в sources как "требует верификации".
Отвечай ТОЛЬКО валидным JSON-массивом без markdown и пояснений до/после JSON.\
"""

USER_PROMPT_TEMPLATE = """\
KPI-цель: {kpi_goal}
Ограничения: {constraints}

Ключевые потери по данным Excel (хвосты):
{top_losses}

Контекст из базы знаний:
{retrieved_context}

Соседние узлы графа:
{graph_context}

Эталонные гипотезы (стиль формулировок организаторов):
{few_shot_examples}

Сгенерируй ровно {n_hypotheses} проверяемых гипотез.
Верни JSON-массив объектов со полями:
- title: кратко, 1 строка (как у технолога)
- full_statement: «Если [X], то [Y на KPI], потому что [Z]»
- mechanism: механизм влияния
- kpi_impact: ожидаемый эффект на KPI (без выдуманных чисел, если их нет в контексте)
- verification_steps: массив из 1-2 шагов проверки
- sources: массив объектов {{file, sheet?, row?, page?, fragment?}} — только из контекста
- risks: массив технических и экономических рисков\
"""


def build_messages(
    *,
    kpi_goal: str,
    constraints: str,
    retrieved_context: str,
    graph_context: str,
    few_shot_examples: str,
    top_losses: str,
    n_hypotheses: int = 7,
) -> list[dict[str, str]]:
    user_text = USER_PROMPT_TEMPLATE.format(
        kpi_goal=kpi_goal or "снизить потери металла в хвостах",
        constraints=constraints or "не указаны",
        retrieved_context=retrieved_context,
        graph_context=graph_context,
        few_shot_examples=few_shot_examples,
        top_losses=top_losses,
        n_hypotheses=n_hypotheses,
    )
    return [
        {"role": "system", "text": SYSTEM_PROMPT},
        {"role": "user", "text": user_text},
    ]
