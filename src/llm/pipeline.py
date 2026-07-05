from __future__ import annotations

from pathlib import Path
from typing import Any

from src.graph.builder import GraphBuilder
from src.graph.scorer import HypothesisScorer, ScoreWeights
from src.llm.feedback_refine import refine_hypothesis
from src.llm.hypothesis_generator import generate_hypotheses
from src.llm.prior_art import nearest_prior_art
from src.llm.yandex_client import YandexGPTClient
from src.models.schemas import GeneratedHypothesis, HypothesisScores, PipelineResult
from src.ui.display import format_novelty_explanation
from src.rag.context import retrieve_context
from src.rag.retriever import ChromaRetriever

DEFAULT_PROCESSED = Path(__file__).resolve().parents[2] / "data" / "processed"
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
    prior_art_snippet: str | None,
    prior_art_similarity: float,
) -> dict[str, str]:
    n_sources = len(hypothesis.get("sources") or [])
    return {
        "novelty": format_novelty_explanation(
            scores.novelty,
            similarity=prior_art_similarity,
            snippet=prior_art_snippet,
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


def rank_hypotheses(
    hypotheses: list[GeneratedHypothesis],
    *,
    case_id: str,
    kpi_goal: str,
    literature_texts: list[str],
    processed_dir: Path | str = DEFAULT_PROCESSED,
    weights: ScoreWeights | None = None,
    top_k: int = 5,
) -> list[GeneratedHypothesis]:
    graph = GraphBuilder.from_processed_dir(processed_dir, case_id=case_id)
    scorer = HypothesisScorer(graph, weights=weights)
    raw_for_scorer = [h.model_dump() for h in hypotheses]
    scored = scorer.rank(
        raw_for_scorer,
        case_id=case_id,
        kpi_goal=kpi_goal,
        top_k=len(raw_for_scorer),
        literature_texts=literature_texts,
    )

    ranked: list[GeneratedHypothesis] = []
    for item in scored[:top_k]:
        scores = HypothesisScores.model_validate(item["scores"])
        prior_art, prior_sim = nearest_prior_art(item, literature_texts)
        base = {k: v for k, v in item.items() if k != "scores"}
        ranked.append(
            GeneratedHypothesis.model_validate(
                {
                    **base,
                    "scores": scores,
                    "score_explanations": _score_explanations(
                        item, scores, prior_art, prior_sim
                    ),
                    "prior_art_snippet": prior_art,
                    "prior_art_similarity": round(prior_sim, 3),
                }
            )
        )
    return ranked


def run_pipeline(
    case_id: str,
    *,
    kpi_goal: str = "",
    constraints: str = "",
    top_k: int = 5,
    n_generate: int = 7,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    chroma_dir: Path | str = DEFAULT_CHROMA,
    use_chroma: bool = True,
    client: YandexGPTClient | None = None,
    weights: ScoreWeights | None = None,
    two_step: bool = False,
) -> PipelineResult:
    processed_dir = Path(processed_dir)
    chroma_dir = Path(chroma_dir)

    if not kpi_goal:
        from src.rag.context import CASE_DEFAULT_KPI

        kpi_goal = CASE_DEFAULT_KPI.get(case_id, "снизить потери металла в хвостах")

    chroma = get_chroma_retriever(chroma_dir) if use_chroma else None
    context = retrieve_context(
        case_id,
        kpi_goal,
        processed_dir=processed_dir,
        chroma_retriever=chroma,
        use_chroma=use_chroma,
    )
    kpi_goal = context.kpi_goal
    literature_texts = context.literature_texts()
    summary = {
        "top_losses": context.top_losses[:3],
        "format_examples_loaded": bool(context.format_examples),
        "graph_triplet_count": len(context.graph_triplets),
        "text_chunk_count": len(context.text_chunks),
        "retrieval_backend": context.retrieval_backend,
        "chroma_doc_count": context.chroma_doc_count,
        "two_step": two_step,
    }

    client = client or YandexGPTClient()

    generated = generate_hypotheses(
        context,
        constraints=constraints,
        client=client,
        n_hypotheses=n_generate,
        two_step=two_step,
    )

    ranked = rank_hypotheses(
        generated,
        case_id=case_id,
        kpi_goal=kpi_goal,
        literature_texts=literature_texts,
        processed_dir=processed_dir,
        weights=weights,
        top_k=top_k,
    )

    return PipelineResult(
        case_id=case_id,
        case_name=context.case_name,
        kpi_goal=kpi_goal,
        mode="live",
        hypotheses=ranked,
        context_summary=summary,
    )


def refine_hypothesis_in_result(
    result: PipelineResult,
    hypothesis_index: int,
    user_comment: str,
    *,
    constraints: str = "",
    weights: ScoreWeights | None = None,
    use_chroma: bool = True,
    processed_dir: Path | str = DEFAULT_PROCESSED,
    chroma_dir: Path | str = DEFAULT_CHROMA,
    client: YandexGPTClient | None = None,
) -> PipelineResult:
    """Replace one hypothesis with an LLM-refined version based on user feedback."""
    processed_dir = Path(processed_dir)
    chroma_dir = Path(chroma_dir)
    if hypothesis_index < 0 or hypothesis_index >= len(result.hypotheses):
        raise IndexError("hypothesis_index out of range")

    chroma = get_chroma_retriever(chroma_dir) if use_chroma else None
    context = retrieve_context(
        result.case_id,
        result.kpi_goal,
        processed_dir=processed_dir,
        chroma_retriever=chroma,
        use_chroma=use_chroma,
    )
    original = result.hypotheses[hypothesis_index]
    refined = refine_hypothesis(
        context,
        original,
        user_comment,
        constraints=constraints,
        client=client,
    )

    refined_scored = rank_hypotheses(
        [refined],
        case_id=result.case_id,
        kpi_goal=result.kpi_goal,
        literature_texts=context.literature_texts(),
        processed_dir=processed_dir,
        weights=weights,
        top_k=1,
    )[0]

    hypotheses = list(result.hypotheses)
    hypotheses[hypothesis_index] = refined_scored

    summary = dict(result.context_summary or {})
    summary["last_refine"] = {
        "index": hypothesis_index,
        "original_title": original.title,
        "refined_title": refined_scored.title,
        "comment": user_comment.strip(),
    }

    return PipelineResult(
        case_id=result.case_id,
        case_name=result.case_name,
        kpi_goal=result.kpi_goal,
        mode=result.mode,
        hypotheses=hypotheses,
        context_summary=summary,
        error=result.error,
    )
