from __future__ import annotations

SYSTEM_PROMPT = """\
Ты — инженер-технолог обогатительной фабрики Норильского никеля.
Твоя задача — СИНТЕЗИРОВАТЬ НОВЫЕ проверяемые гипотезы по снижению потерь металлов в хвостах.

КРИТИЧЕСКИ ВАЖНО:
- Каждая гипотеза — конкретная комбинация: класс крупности / минерал / потери из Excel + техническое вмешательство из литературы или графа.
- НЕ повторяй формулировки из раздела «Направления для синтеза» дословно — используй их как отправную точку для НОВЫХ комбинаций.
- Примеры формулировок от организаторов показывают только СТИЛЬ и уровень конкретности; содержание бери из Excel и литературы.
- Источники (sources): обязательно укажи Excel (Хвосты *.xlsx) и/или литературу (geokniga*.pdf) с file/sheet/row/page.
- Если в контексте есть блок «из интернета» — добавь отдельный источник: file = URL из контекста, fragment = «требует верификации».
- Используй ТОЛЬКО факты из контекста. Не выдумывай цифры.
- Если данных недостаточно, укажи это в sources как "требует верификации".
- Отвечай ТОЛЬКО валидным JSON-массивом без markdown и пояснений до/после JSON."""

USER_PROMPT_TEMPLATE = """\
KPI-цель: {kpi_goal}
Ограничения: {constraints}

Ключевые потери по данным Excel (хвосты) — ОСНОВА для гипотез:
{top_losses}

Контекст из базы знаний (литература, отчёты):
{retrieved_context}

Соседние узлы графа (минералы, классы крупности, процессы):
{graph_context}

Направления для синтеза (собраны из Excel + графа, НЕ готовые ответы):
{synthesis_hints}

{format_examples}

{web_context}

Сгенерируй ровно {n_hypotheses} НОВЫХ проверяемых гипотез.
Каждая гипотеза должна отличаться от других по механизму и целевому узлу (класс крупности / минерал / операция).

Верни JSON-массив объектов со полями:
- title: кратко, 1 строка (как у технолога)
- full_statement: «Если [конкретное вмешательство], то [эффект на KPI], потому что [данные из Excel/графа]»
- mechanism: механизм влияния
- kpi_impact: ожидаемый эффект на KPI (без выдуманных чисел, если их нет в контексте)
- verification_steps: массив из 1-2 шагов проверки
- sources: массив объектов {{file, sheet?, row?, page?, fragment?}} — Excel, литература; для идей из интернета укажи file как URL и fragment «требует верификации»
- risks: массив технических и экономических рисков"""

STEP1_SYSTEM = """\
Ты — инженер-технолог обогатительной фабрики. Проанализируй контекст и найди НЕОЧЕВИДНЫЕ рычаги снижения потерь.
Не копируй готовые формулировки — предложи новые комбинации узел потерь + вмешательство + механизм.
Ответ — ТОЛЬКО JSON-массив без markdown."""

STEP1_USER_TEMPLATE = """\
KPI-цель: {kpi_goal}
Ограничения: {constraints}

Потери Excel:
{top_losses}

База знаний:
{retrieved_context}

Граф:
{graph_context}

Направления синтеза (не копировать дословно):
{synthesis_hints}

{web_context}

Верни JSON-массив из {n_levers} объектов:
- target_loss: узел/класс потерь из Excel
- intervention: конкретное техническое вмешательство
- mechanism: почему это может снизить потери
- data_anchor: отсылка к файлу/строке/фрагменту из контекста
- distinct_from: чем отличается от типовых решений"""

STEP2_USER_LEVERS = """\
Найденные рычаги (шаг 1 — используй как основу, разверни в полные гипотезы):
{levers_json}

"""


def _context_user_block(
    *,
    kpi_goal: str,
    constraints: str,
    retrieved_context: str,
    graph_context: str,
    synthesis_hints: str,
    top_losses: str,
    format_examples: str = "",
    web_context: str = "",
) -> str:
    examples_block = format_examples.strip() or (
        "Примеры стиля: конкретное техническое вмешательство + целевой узел процесса."
    )
    web_block = web_context.strip()
    return (
        f"KPI-цель: {kpi_goal or 'снизить потери металла в хвостах'}\n"
        f"Ограничения: {constraints or 'не указаны'}\n\n"
        f"Ключевые потери по данным Excel (хвосты) — ОСНОВА для гипотез:\n{top_losses}\n\n"
        f"Контекст из базы знаний (литература, отчёты):\n{retrieved_context}\n\n"
        f"Соседние узлы графа (минералы, классы крупности, процессы):\n{graph_context}\n\n"
        f"Направления для синтеза (собраны из Excel + графа, НЕ готовые ответы):\n{synthesis_hints}\n\n"
        f"{examples_block}\n\n{web_block}"
    ).strip()


def build_brainstorm_messages(
    *,
    kpi_goal: str,
    constraints: str,
    retrieved_context: str,
    graph_context: str,
    synthesis_hints: str,
    top_losses: str,
    web_context: str = "",
    n_levers: int = 7,
) -> list[dict[str, str]]:
    user_text = STEP1_USER_TEMPLATE.format(
        kpi_goal=kpi_goal or "снизить потери металла в хвостах",
        constraints=constraints or "не указаны",
        top_losses=top_losses,
        retrieved_context=retrieved_context,
        graph_context=graph_context,
        synthesis_hints=synthesis_hints,
        web_context=web_context.strip(),
        n_levers=n_levers,
    )
    return [
        {"role": "system", "text": STEP1_SYSTEM},
        {"role": "user", "text": user_text},
    ]


def build_messages(
    *,
    kpi_goal: str,
    constraints: str,
    retrieved_context: str,
    graph_context: str,
    synthesis_hints: str,
    top_losses: str,
    format_examples: str = "",
    web_context: str = "",
    n_hypotheses: int = 7,
    levers_json: str = "",
) -> list[dict[str, str]]:
    context_block = _context_user_block(
        kpi_goal=kpi_goal,
        constraints=constraints,
        retrieved_context=retrieved_context,
        graph_context=graph_context,
        synthesis_hints=synthesis_hints,
        top_losses=top_losses,
        format_examples=format_examples,
        web_context=web_context,
    )
    levers_block = ""
    if levers_json.strip():
        levers_block = STEP2_USER_LEVERS.format(levers_json=levers_json.strip())

    user_text = (
        f"{context_block}\n\n{levers_block}"
        f"Сгенерируй ровно {n_hypotheses} НОВЫХ проверяемых гипотез.\n"
        f"Каждая гипотеза должна отличаться от других по механизму и целевому узлу.\n\n"
        f"Верни JSON-массив объектов со полями:\n"
        f"- title, full_statement, mechanism, kpi_impact, verification_steps, sources, risks"
    )
    return [
        {"role": "system", "text": SYSTEM_PROMPT},
        {"role": "user", "text": user_text},
    ]
