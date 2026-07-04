from __future__ import annotations

import json
import re
import time
from typing import Any

from pydantic import ValidationError

from src.llm.prompts import build_brainstorm_messages, build_messages
from src.llm.synthesis import build_synthesis_candidates
from src.llm.yandex_client import YandexGPTClient
from src.models.schemas import GeneratedHypothesis, SourceRef
from src.rag.context import RetrievalContext
from src.ui.source_downloads import split_source_location


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


def _coerce_source(raw: Any) -> SourceRef | dict[str, Any]:
    if isinstance(raw, str):
        parsed = split_source_location({"file": raw})
    elif isinstance(raw, dict):
        parsed = split_source_location(raw)
    else:
        return SourceRef(file="требует верификации")

    return SourceRef(
        file=str(parsed.get("file") or "требует верификации"),
        sheet=parsed.get("sheet"),
        row=parsed.get("row"),
        page=parsed.get("page"),
        fragment=parsed.get("fragment"),
    )


def _is_hypothesis_doc_source(file_name: str) -> bool:
    lowered = file_name.lower()
    return "гипотез" in lowered or "hypothesis" in lowered


def parse_hypotheses(raw_items: list[Any]) -> list[GeneratedHypothesis]:
    parsed: list[GeneratedHypothesis] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        sources_raw = item.get("sources") or []
        if isinstance(sources_raw, str):
            sources_raw = [{"file": sources_raw}]
        sources = [
            _coerce_source(s)
            for s in sources_raw
            if not _is_hypothesis_doc_source(
                s if isinstance(s, str) else str((s or {}).get("file", ""))
            )
        ]

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


def _dedupe_hypotheses(hypotheses: list[GeneratedHypothesis]) -> list[GeneratedHypothesis]:
    seen: set[str] = set()
    unique: list[GeneratedHypothesis] = []
    for item in hypotheses:
        key = item.title.lower().strip()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def generate_hypotheses(
    context: RetrievalContext,
    *,
    constraints: str = "",
    client: YandexGPTClient | None = None,
    n_hypotheses: int = 7,
    temperature: float = 0.55,
    two_step: bool = False,
    step_pause_sec: float = 8.0,
) -> list[GeneratedHypothesis]:
    client = client or YandexGPTClient()
    prompt_parts = context.to_prompt_dict()
    levers_json = ""

    if two_step:
        brainstorm = build_brainstorm_messages(
            kpi_goal=context.kpi_goal,
            constraints=constraints,
            n_levers=n_hypotheses,
            **{k: v for k, v in prompt_parts.items() if k != "format_examples"},
        )
        raw_levers = client.complete(
            brainstorm, temperature=0.45, max_tokens=3500
        )
        try:
            levers = extract_json_array(raw_levers)
            levers_json = json.dumps(levers, ensure_ascii=False, indent=2)
        except ValueError:
            levers_json = ""
        if step_pause_sec > 0:
            time.sleep(step_pause_sec)

    messages = build_messages(
        kpi_goal=context.kpi_goal,
        constraints=constraints,
        n_hypotheses=n_hypotheses,
        levers_json=levers_json,
        **prompt_parts,
    )
    raw_text = client.complete(messages, temperature=temperature, max_tokens=7000)
    raw_items = extract_json_array(raw_text)
    parsed = _dedupe_hypotheses(parse_hypotheses(raw_items))

    if len(parsed) < n_hypotheses:
        synthesized = build_synthesis_candidates(
            context.case_id,
            context.kpi_goal,
            n_candidates=n_hypotheses,
        )
        for item in synthesized:
            if len(parsed) >= n_hypotheses:
                break
            if item.title.lower() in {h.title.lower() for h in parsed}:
                continue
            parsed.append(item)

    return parsed[:n_hypotheses]
