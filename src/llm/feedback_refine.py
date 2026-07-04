from __future__ import annotations

import json
import re
from typing import Any

from src.llm.hypothesis_generator import parse_hypotheses
from src.llm.yandex_client import YandexGPTClient
from src.models.schemas import GeneratedHypothesis
from src.rag.context import RetrievalContext
from src.feedback.store import format_feedback_lessons


REFINE_SYSTEM = """\
Ты — инженер-технолог обогатительной фабрики. Пользователю не понравилась гипотеза — улучши её.
Сохрани проверяемый формат If-Then-Because, опирайся на контекст и замечание.
Не копируй дословно старую версию — исправь слабые места.
Источники только из контекста (Excel, PDF, OCR-схемы PNG, OCR-страницы PDF); иначе «требует верификации».
Ответ — ТОЛЬКО один JSON-объект гипотезы без markdown."""

REFINE_USER_TEMPLATE = """\
KPI-цель: {kpi_goal}
Ограничения: {constraints}

Контекст (фрагмент):
{context_excerpt}

{feedback_lessons}

Исходная гипотеза (не устраивает пользователя):
{original_json}

Замечание пользователя:
{user_comment}

Верни улучшенный JSON-объект с полями:
title, full_statement, mechanism, kpi_impact, verification_steps, sources, risks"""


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0]
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("LLM response does not contain a JSON object")


def refine_hypothesis(
    context: RetrievalContext,
    original: GeneratedHypothesis,
    user_comment: str,
    *,
    constraints: str = "",
    client: YandexGPTClient | None = None,
    temperature: float = 0.4,
) -> GeneratedHypothesis:
    if not user_comment.strip():
        raise ValueError("Нужен текст замечания пользователя")

    client = client or YandexGPTClient()
    prompt_parts = context.to_prompt_dict()
    context_excerpt = (
        f"{prompt_parts.get('top_losses', '')[:1200]}\n\n"
        f"{prompt_parts.get('retrieved_context', '')[:2000]}\n\n"
        f"{prompt_parts.get('synthesis_hints', '')[:800]}"
    )
    lessons = format_feedback_lessons(context.case_id)

    user_text = REFINE_USER_TEMPLATE.format(
        kpi_goal=context.kpi_goal,
        constraints=constraints or "не указаны",
        context_excerpt=context_excerpt,
        feedback_lessons=lessons,
        original_json=json.dumps(original.model_dump(), ensure_ascii=False, indent=2),
        user_comment=user_comment.strip(),
    )
    messages = [
        {"role": "system", "text": REFINE_SYSTEM},
        {"role": "user", "text": user_text},
    ]
    raw = client.complete(messages, temperature=temperature, max_tokens=2500)
    item = _extract_json_object(raw)
    parsed = parse_hypotheses([item])
    if not parsed:
        raise ValueError("Не удалось разобрать улучшенную гипотезу")
    refined = parsed[0]
    refined.scores = None
    refined.score_explanations = {}
    refined.prior_art_snippet = None
    refined.prior_art_similarity = None
    return refined
