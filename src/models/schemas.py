from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    PLANT = "Plant"
    MATERIAL = "Material"
    ELEMENT = "Element"
    SIZE_CLASS = "SizeClass"
    MINERAL = "Mineral"
    PROCESS = "Process"
    EQUIPMENT = "Equipment"
    METRIC = "Metric"
    HYPOTHESIS = "Hypothesis"
    SOURCE = "Source"


class SourceRef(BaseModel):
    file: str
    sheet: str | None = None
    row: int | None = None
    page: int | None = None
    fragment: str | None = None


class Triplet(BaseModel):
    subject: str
    subject_type: NodeType
    predicate: str
    object: str
    object_type: NodeType
    source: SourceRef
    case_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextChunk(BaseModel):
    chunk_id: str
    text: str
    source: SourceRef
    case_id: str | None = None
    chunk_type: str = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceHypothesis(BaseModel):
    index: int
    title: str
    case_id: str
    source: SourceRef


class CaseIngestResult(BaseModel):
    case_id: str
    case_name: str
    triplets: list[Triplet] = Field(default_factory=list)
    hypotheses: list[ReferenceHypothesis] = Field(default_factory=list)
    chunks: list[TextChunk] = Field(default_factory=list)


class IngestResult(BaseModel):
    cases: list[CaseIngestResult] = Field(default_factory=list)
    literature_chunks: list[TextChunk] = Field(default_factory=list)
    instruction_chunks: list[TextChunk] = Field(default_factory=list)
    total_triplets: int = 0
    total_chunks: int = 0


class HypothesisScores(BaseModel):
    novelty: float = Field(ge=0, le=1)
    groundedness: float = Field(ge=0, le=1)
    risk: float = Field(ge=0, le=1)
    value: float = Field(ge=0, le=1)
    total: float = Field(ge=0, le=1)


class GeneratedHypothesis(BaseModel):
    title: str
    full_statement: str
    mechanism: str | None = None
    kpi_impact: str | None = None
    verification_steps: list[str] = Field(default_factory=list)
    sources: list[SourceRef | dict[str, Any]] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    scores: HypothesisScores | None = None
    score_explanations: dict[str, str] = Field(default_factory=dict)
    prior_art_snippet: str | None = None
    prior_art_similarity: float | None = None


class PipelineResult(BaseModel):
    case_id: str
    case_name: str
    kpi_goal: str
    mode: str
    hypotheses: list[GeneratedHypothesis] = Field(default_factory=list)
    context_summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
