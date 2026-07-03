from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any

from pydantic import ValidationError

from src.llm.prompts import build_messages
from src.llm.yandex_client import YandexGPTClient
from src.models.schemas import GeneratedHypothesis, SourceRef
from src.rag.context import RetrievalContext


def extract_json_array(text: str) -> list[Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        payload = json.loads(text)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and "hypotheses" in payload:
            hyps = payload["hypotheses"]
            return hyps if isinstance(hyps, list) else [hyps]
    except json.JSONDecodeError:
        pass

    match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("LLM response does not contain a JSON array of hypotheses")


def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value == int(value) else None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            num = float(value)
            return int(num) if num == int(num) else None
        except ValueError:
            return None
    return None


def _coerce_source(raw: Any) -> SourceRef | dict[str, Any]:
    if isinstance(raw, str):
        return SourceRef(file=raw)
    if isinstance(raw, dict):
        return SourceRef(
            file=str(raw.get("file") or raw.get("filename") or "требует верификации"),
            sheet=raw.get("sheet"),
            row=_coerce_int(raw.get("row")),
            page=_coerce_int(raw.get("page")),
            fragment=raw.get("fragment"),
        )
    return SourceRef(file="требует верификации")


def parse_hypotheses(raw_items: list[Any]) -> list[GeneratedHypothesis]:
    parsed: list[GeneratedHypothesis] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        sources_raw = item.get("sources") or []
        if isinstance(sources_raw, str):
            sources_raw = [{"file": sources_raw}]
        sources = [_coerce_source(s) for s in sources_raw]

        verification = item.get("verification_steps") or item.get("verification") or []
        if isinstance(verification, str):
            verification = [verification]

        risks = item.get("risks") or []
        if isinstance(risks, str):
            risks = [risks]

        payload = {
            "title": str(item.get("title") or item.get("name") or "").strip(),
            "full_statement": str(
                item.get("full_statement") or item.get("statement") or ""
            ).strip(),
            "mechanism": item.get("mechanism"),
            "kpi_impact": item.get("kpi_impact"),
            "verification_steps": verification,
            "sources": sources,
            "risks": risks,
        }
        if not payload["title"] or not payload["full_statement"]:
            continue
        try:
            parsed.append(GeneratedHypothesis.model_validate(payload))
        except ValidationError:
            continue
    return parsed


def nearest_reference(
    hypothesis: GeneratedHypothesis | dict[str, Any],
    references: list[str],
) -> tuple[str | None, float]:
    if isinstance(hypothesis, GeneratedHypothesis):
        text = " ".join(
            part for part in [hypothesis.title, hypothesis.full_statement] if part
        )
    else:
        text = " ".join(
            part
            for part in [hypothesis.get("title"), hypothesis.get("full_statement")]
            if part
        )
    if not references or not text:
        return None, 0.0
    best_title = references[0]
    best_ratio = 0.0
    for ref in references:
        ratio = SequenceMatcher(None, text.lower(), ref.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_title = ref
    return best_title, best_ratio


def generate_hypotheses(
    context: RetrievalContext,
    *,
    constraints: str = "",
    client: YandexGPTClient | None = None,
    n_hypotheses: int = 7,
    temperature: float = 0.35,
) -> list[GeneratedHypothesis]:
    client = client or YandexGPTClient()
    prompt_parts = context.to_prompt_dict()
    messages = build_messages(
        kpi_goal=context.kpi_goal,
        constraints=constraints,
        n_hypotheses=n_hypotheses,
        **prompt_parts,
    )
    raw_text = client.complete(messages, temperature=temperature, max_tokens=7000)
    raw_items = extract_json_array(raw_text)
    return parse_hypotheses(raw_items)
