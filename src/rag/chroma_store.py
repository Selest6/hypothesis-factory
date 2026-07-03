from __future__ import annotations

from pathlib import Path

from src.rag.retriever import ChromaRetriever

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHROMA_DIR = ROOT / "data" / "chroma"
DEFAULT_EMBEDDINGS_FILE = ROOT / "data" / "processed" / "embeddings.json"
EXPECTED_DOC_COUNT = 3076


def chroma_is_ready(chroma_dir: Path = DEFAULT_CHROMA_DIR, min_count: int = 1000) -> bool:
    if not chroma_dir.exists():
        return False
    try:
        return ChromaRetriever(chroma_dir).count() >= min_count
    except Exception:
        return False


def build_chroma_index(
    *,
    chroma_dir: Path = DEFAULT_CHROMA_DIR,
    embeddings_file: Path = DEFAULT_EMBEDDINGS_FILE,
    reset: bool = False,
    batch_size: int = 128,
) -> ChromaRetriever:
    if not embeddings_file.exists():
        raise FileNotFoundError(
            f"Embeddings file not found: {embeddings_file}. "
            "Run: python scripts/build_embeddings.py"
        )

    items = ChromaRetriever.load_embeddings_file(embeddings_file)
    if not items:
        raise ValueError(f"No items in {embeddings_file}")

    retriever = ChromaRetriever(persist_dir=chroma_dir)
    if reset or retriever.count() == 0:
        if reset:
            retriever.reset()
        print(f"Loading {len(items)} vectors into ChromaDB...")
        retriever.upsert_precomputed(items, batch_size=batch_size)
    return retriever


def ensure_chroma_index(
    *,
    chroma_dir: Path = DEFAULT_CHROMA_DIR,
    embeddings_file: Path = DEFAULT_EMBEDDINGS_FILE,
    min_count: int = 1000,
) -> ChromaRetriever | None:
    """Return Chroma retriever, building index from embeddings.json if needed."""
    if not embeddings_file.exists():
        return None

    if chroma_is_ready(chroma_dir, min_count=min_count):
        return ChromaRetriever(chroma_dir)

    try:
        return build_chroma_index(
            chroma_dir=chroma_dir,
            embeddings_file=embeddings_file,
            reset=False,
        )
    except Exception as exc:
        print(f"ChromaDB unavailable: {exc}")
        return None


def get_chroma_retriever(
    chroma_dir: Path | str | None = None,
    *,
    auto_build: bool = True,
) -> ChromaRetriever | None:
    path = Path(chroma_dir) if chroma_dir else DEFAULT_CHROMA_DIR
    if auto_build:
        return ensure_chroma_index(chroma_dir=path)
    if chroma_is_ready(path):
        return ChromaRetriever(path)
    return None
