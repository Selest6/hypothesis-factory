from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from src.graph.builder import GraphBuilder
from src.graph.scorer import HypothesisScorer, ScoreWeights
from src.llm.hypothesis_generator import generate_hypotheses, nearest_reference
from src.llm.synthesis import build_synthesis_candidates
from src.llm.yandex_client import YandexGPTClient, YandexGPTError
from src.models.schemas import GeneratedHypothesis, HypothesisScores, PipelineResult
from src.rag.context import retrieve_context
from src.rag.retriever import ChromaRetriever

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
DEFAULT_CHROMA = Path(__file__).resolve().parents[2] / "data" / "chroma"


def get_chroma_retriever(chroma_dir: Path | str = DEFAULT_CHROMA) -> ChromaRetriever | None:
    """Return Chroma retriever if index exists and is non-empty."""
    chroma_dir = Path(chroma_dir)
    if not (chroma_dir / "index_manifest.json").exists():
        return None
    try:
        retriever = ChromaRetriever(persist_dir=chroma_dir)
        if retriever.count() <= 0:
            return None
        return retriever
    except Exception:
        return None


def _score_explanations(
    hypothesis: dict[str, Any],
    scores: HypothesisScores,
    nearest_ref: str | None,
    ref_similarity: float,
) -> dict[str, str]:
    n_sources = len(hypothesis.get("sources") or [])
    return {
        "novelty": (
            f"Новизна {scores.novelty:.2f}: "
            f"{'новое направление' if scores.novelty >= 0.6 else 'близко к известным решениям'}"
            + (
                f"; ближайшая эталонная: «{nearest_ref}» (сходство {ref_similarity:.0%})"
                if nearest_ref
                else ""
            )
        ),
        "groundedness": (
            f"Обоснованность {scores.groundedness:.2f}: "
            f"{n_sources} источник(ов) в ответе"
        ),
        "risk": (
            f"Риск {scores.risk:.2f}: "
            f"{'есть неподтверждённые числа или противоречия' if scores.risk >= 0.4 else 'умеренный'}"
        ),
        "value": (
            f"Ценность {scores.value:.2f}: "
            f"близость к KPI-узлам потерь в хвостах"
        ),
    }


def save_cache(
    case_id: str,
    hypotheses: list[GeneratedHypothesis],
    *,
    cache_dir: Path = DEFAULT_CACHE,
    meta: dict[str, Any] | None = None,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{case_id}.json"
    payload = {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": meta or {},
        "hypotheses": [h.model_dump() for h in hypotheses],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_cache(case_id: str, *, cache_dir: Path = DEFAULT_CACHE) -> list[GeneratedHypothesis] | None:
    path = cache_dir / f"{case_id}.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("hypotheses") or []
    return [GeneratedHypothesis.model_validate(item) for item in items]


def load_cache_meta(case_id: str, *, cache_dir: Path = DEFAULT_CACHE) -> dict[str, Any]:
    path = cache_dir / f"{case_id}.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "generated_at": payload.get("generated_at"),
        "meta": payload.get("meta") or {},
    }


def rank_hypotheses(
    hypotheses: list[GeneratedHypothesis],
    *,
    case_id: str,
    kpi_goal: str,
    reference_titles: list[str],
    processed_dir: Path | str = DEFAULT_PROCESSED,
    weights: ScoreWeights | None = None,
    top_k: int = 5,
) -> list[GeneratedHypothesis]:
    graph = GraphBuilder.from_processed_dir(processed_dir, case_id=case_id)
    scorer = HypothesisScorer(graph, weights=weights)
    raw_for_scorer = [h.model_dump() for h in hypotheses]
    scored = scorer.rank(raw_for_scorer, case_id=case_id, kpi_goal=kpi_goal, top_k=len(raw_for_scorer))

    ranked: list[GeneratedHypothesis] = []
    for item in scored[:top_k]:
        scores = HypothesisScores.model_validate(item["scores"])
        nearest_ref, ref_sim = nearest_reference(item, reference_titles)
        base = {k: v for k, v in item.items() if k != "scores"}
        ranked.append(
            GeneratedHypothesis.model_validate(
                {
                    **base,
                    "scores": scores,
                    "score_explanations": _score_explanations(item, scores, nearest_ref, ref_sim),
                    "nearest_reference": nearest_ref,
                    "reference_similarity": round(ref_sim, 3),
                }
            )
        )
    return ranked


def run_pipeline(
    case_id: str,
    *,
    kpi_goal: str = "",
    constraints: str = "",
    mode: Literal["live", "demo", "offline"] = "live",
    top_k: int = 5,
    n_generate: int = 7,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    cache_dir: Path | str = DEFAULT_CACHE,
    chroma_dir: Path | str = DEFAULT_CHROMA,
    use_chroma: bool = True,
    client: YandexGPTClient | None = None,
    weights: ScoreWeights | None = None,
    save_demo_cache: bool = True,
) -> PipelineResult:
    processed_dir = Path(processed_dir)
    cache_dir = Path(cache_dir)
    chroma_dir = Path(chroma_dir)

    chroma = get_chroma_retriever(chroma_dir) if use_chroma else None
    context = retrieve_context(
        case_id,
        kpi_goal,
        processed_dir=processed_dir,
        chroma_retriever=chroma,
    )
    kpi_goal = context.kpi_goal
    summary = {
        "top_losses": context.top_losses[:3],
        "reference_count": len(context.reference_hypotheses),
        "graph_triplet_count": len(context.graph_triplets),
        "text_chunk_count": len(context.text_chunks),
        "retrieval_backend": context.retrieval_backend,
        "chroma_doc_count": context.chroma_doc_count,
    }

    if mode == "demo":
        cached = load_cache(case_id, cache_dir=cache_dir)
        if cached:
            return PipelineResult(
                case_id=case_id,
                case_name=context.case_name,
                kpi_goal=kpi_goal,
                mode="demo",
                hypotheses=cached,
                context_summary=summary,
            )

    if mode == "offline":
        generated = build_synthesis_candidates(
            case_id, kpi_goal, processed_dir=processed_dir, n_candidates=n_generate
        )
        ranked = rank_hypotheses(
            generated,
            case_id=case_id,
            kpi_goal=kpi_goal,
            reference_titles=context.reference_hypotheses,
            processed_dir=processed_dir,
            weights=weights,
            top_k=top_k,
        )
        if save_demo_cache and ranked:
            save_cache(
                case_id,
                ranked,
                cache_dir=cache_dir,
                meta={"kpi_goal": kpi_goal, "constraints": constraints, "source": "offline"},
            )
        return PipelineResult(
            case_id=case_id,
            case_name=context.case_name,
            kpi_goal=kpi_goal,
            mode="offline",
            hypotheses=ranked,
            context_summary=summary,
        )

    client = client or YandexGPTClient()
    used_mode = "live"
    error: str | None = None

    try:
        generated = generate_hypotheses(
            context,
            constraints=constraints,
            client=client,
            n_hypotheses=n_generate,
        )
    except YandexGPTError as exc:
        cached = load_cache(case_id, cache_dir=cache_dir)
        if cached:
            return PipelineResult(
                case_id=case_id,
                case_name=context.case_name,
                kpi_goal=kpi_goal,
                mode="demo_fallback",
                hypotheses=cached,
                context_summary=summary,
                error=str(exc),
            )
        generated = build_synthesis_candidates(
            case_id, kpi_goal, processed_dir=processed_dir, n_candidates=n_generate
        )
        ranked = rank_hypotheses(
            generated,
            case_id=case_id,
            kpi_goal=kpi_goal,
            reference_titles=context.reference_hypotheses,
            processed_dir=processed_dir,
            weights=weights,
            top_k=top_k,
        )
        if save_demo_cache and ranked:
            save_cache(
                case_id,
                ranked,
                cache_dir=cache_dir,
                meta={"kpi_goal": kpi_goal, "constraints": constraints, "source": "synthesis_fallback"},
            )
        return PipelineResult(
            case_id=case_id,
            case_name=context.case_name,
            kpi_goal=kpi_goal,
            mode="synthesis_fallback",
            hypotheses=ranked,
            context_summary=summary,
            error=str(exc),
        )

    ranked = rank_hypotheses(
        generated,
        case_id=case_id,
        kpi_goal=kpi_goal,
        reference_titles=context.reference_hypotheses,
        processed_dir=processed_dir,
        weights=weights,
        top_k=top_k,
    )

    if save_demo_cache and ranked:
        save_cache(
            case_id,
            ranked,
            cache_dir=cache_dir,
            meta={"kpi_goal": kpi_goal, "constraints": constraints},
        )

    return PipelineResult(
        case_id=case_id,
        case_name=context.case_name,
        kpi_goal=kpi_goal,
        mode=used_mode,
        hypotheses=ranked,
        context_summary=summary,
    )
