from __future__ import annotations

from src.rag.reading_guide import load_reading_guide_text

SOURCES_RULES = """\
- Источники (sources) — только из контекста, формат {file, sheet?, row?, page?, fragment?}:
  • Excel (Хвосты *.xlsx): file + sheet + row — фактические потери, минералы, классы крупности
  • Литература PDF (текстовый слой): file + page — методы флотации, обогащения, теория
  • OCR-схемы (PNG/JPG/WebP — регламенты, технологические схемы, списки оборудования): \
file = имя файла из контекста (например «Регламент 1.png»), без sheet/row; fragment — короткая цитата
  • OCR-страницы PDF (отсканированные страницы или схемы внутри PDF без текстового слоя): \
file + page (номер страницы из контекста, как у geokniga*.pdf)
  • Интернет: file = URL из блока «из интернета», fragment = «требует верификации»
- ЗАПРЕЩЕНО указывать в sources файл «Как читать отчет института по хвостам.docx» и любые инструкции по чтению отчётов — это не данные, а мета-описание формата Excel."""

MULTI_SOURCE_RULES = """\
- Все типы источников в контексте РАВНОЦЕННЫ: Excel, PDF, OCR (PNG/страницы PDF), граф, интернет.
- Каждая гипотеза — синтез из нескольких типов, когда они есть в контексте:
  • узел потерь / минерал / класс — из Excel или графа;
  • техническое вмешательство и режим — из PDF, OCR-схем или литературы;
  • обоснование механизма — комбинация Excel/графа + PDF/OCR.
- В sources указывай минимум 2 объекта разных типов (например Excel + PDF, Excel + OCR PNG, PDF + OCR), если в контексте есть оба типа.
- Не ограничивайся только Excel: литература и OCR-схемы — полноценные источники для гипотез."""

SYSTEM_PROMPT = f"""\
Ты — инженер-технолог обогатительной фабрики Норильского никеля.
Твоя задача — СИНТЕЗИРОВАТЬ НОВЫЕ проверяемые гипотезы по снижению потерь металлов в хвостах.

КРИТИЧЕСКИ ВАЖНО:
- Каждая гипотеза — конкретная комбинация узла потерь (Excel/граф) + технического вмешательства (PDF/OCR/литература) + механизма.
- НЕ повторяй формулировки из раздела «Направления для синтеза» дословно — используй их как отправную точку для НОВЫХ комбинаций.
- Примеры формулировок от организаторов показывают только СТИЛЬ и уровень конкретности.
{MULTI_SOURCE_RULES}
{SOURCES_RULES}
- Используй ТОЛЬКО факты из контекста. Не выдумывай цифры.
- Если данных недостаточно, укажи это в sources как "требует верификации".
- Отвечай ТОЛЬКО валидным JSON-массивом без markdown и пояснений до/после JSON."""


def _system_prompt_with_guide() -> str:
    guide = load_reading_guide_text()
    if not guide.strip():
        return SYSTEM_PROMPT
    return f"{SYSTEM_PROMPT}\n\n{guide}"


USER_PROMPT_TEMPLATE = """\
KPI-цель: {kpi_goal}
Ограничения: {constraints}

Потери и минералогия по отчётам Excel (хвосты):
{top_losses}

Литература, OCR-схемы (PNG), OCR-страницы PDF, отчёты:
{retrieved_context}

Соседние узлы графа (минералы, классы крупности, процессы):
{graph_context}

Направления для синтеза (собраны из всех источников, НЕ готовые ответы):
{synthesis_hints}

{format_examples}

{web_context}

Сгенерируй ровно {n_hypotheses} НОВЫХ проверяемых гипотез.
Каждая гипотеза должна отличаться от других по механизму и целевому узлу (класс крупности / минерал / операция).
У каждой гипотезы — минимум 2 источника разных типов (Excel/PDF/OCR), если они есть в контексте.

Верни JSON-массив объектов со полями:
- title: кратко, 1 строка (как у технолога)
- full_statement: «Если [вмешательство из PDF/OCR/литературы], то [эффект на KPI], потому что [факты из Excel/графа + механизм из PDF/OCR]»
- mechanism: механизм влияния
- kpi_impact: ожидаемый эффект на KPI (без выдуманных чисел, если их нет в контексте)
- verification_steps: массив из 1-2 шагов проверки
- sources: массив из 2+ объектов {{file, sheet?, row?, page?, fragment?}} разных типов — Excel, PDF, OCR PNG, OCR PDF page; для интернета file = URL
- risks: массив технических и экономических рисков"""

STEP1_SYSTEM = """\
Ты — инженер-технолог обогатительной фабрики. Проанализируй контекст и найди НЕОЧЕВИДНЫЕ рычаги снижения потерь.
Комбинируй Excel/граф (узлы потерь) с PDF/OCR (вмешательства и режимы). Не копируй готовые формулировки.
Ответ — ТОЛЬКО JSON-массив без markdown."""

STEP1_USER_TEMPLATE = """\
KPI-цель: {kpi_goal}
Ограничения: {constraints}

Потери и минералогия (Excel):
{top_losses}

Литература, OCR-схемы, OCR-страницы PDF:
{retrieved_context}

Граф:
{graph_context}

Направления синтеза (не копировать дословно):
{synthesis_hints}

{web_context}

Верни JSON-массив из {n_levers} объектов:
- target_loss: узел/класс потерь (Excel или граф)
- intervention: конкретное вмешательство (PDF, OCR-схема, литература)
- mechanism: почему это может снизить потери
- data_anchor: отсылка к файлу/строке/странице/фрагменту — укажи тип (Excel / PDF / OCR)
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
        f"Потери и минералогия по отчётам Excel (хвосты):\n{top_losses}\n\n"
        f"Литература, OCR-схемы (PNG), OCR-страницы PDF, отчёты:\n{retrieved_context}\n\n"
        f"Соседние узлы графа (минералы, классы крупности, процессы):\n{graph_context}\n\n"
        f"Направления для синтеза (собраны из всех источников, НЕ готовые ответы):\n{synthesis_hints}\n\n"
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
        f"Каждая гипотеза должна отличаться от других по механизму и целевому узлу.\n"
        f"У каждой гипотезы — минимум 2 источника разных типов (Excel/PDF/OCR), если они есть в контексте.\n\n"
        f"Верни JSON-массив объектов со полями:\n"
        f"- title, full_statement, mechanism, kpi_impact, verification_steps, "
        f"sources (2+ объектов разных типов: Excel / PDF / OCR PNG / OCR PDF page), risks"
    )
    return [
        {"role": "system", "text": _system_prompt_with_guide()},
        {"role": "user", "text": user_text},
    ]
