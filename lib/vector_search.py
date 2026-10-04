from typing import Any, Callable, TypedDict

from lib.embeddings import embed_query as default_embed_query
from lib.store import load_chunks


class StoredEmbedding(TypedDict, total=False):
    text: str
    embedding: list[float]
    metadata: dict[str, Any]


class RetrievedDocument(TypedDict):
    pageContent: str
    metadata: dict[str, Any]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for i in range(len(a)):
        dot += a[i] * b[i]
        norm_a += a[i] * a[i]
        norm_b += b[i] * b[i]

    denom = (norm_a**0.5) * (norm_b**0.5)
    return 0.0 if denom == 0 else dot / denom


def max_marginal_relevance(
    candidates: list[tuple[StoredEmbedding, float]],
    k: int,
    lambda_: float,
) -> list[RetrievedDocument]:
    selected: list[tuple[StoredEmbedding, float]] = []
    remaining = list(candidates)

    while len(selected) < k and remaining:
        best_index = 0
        best_mmr = float("-inf")

        for i, (doc, relevance) in enumerate(remaining):
            max_similarity_to_selected = 0.0
            for picked_doc, _ in selected:
                sim = cosine_similarity(
                    doc["embedding"],
                    picked_doc["embedding"],
                )
                max_similarity_to_selected = max(max_similarity_to_selected, sim)

            mmr = lambda_ * relevance - (1 - lambda_) * max_similarity_to_selected
            if mmr > best_mmr:
                best_mmr = mmr
                best_index = i

        selected.append(remaining.pop(best_index))

    return [
        {
            "pageContent": doc["text"],
            "metadata": {
                **(doc.get("metadata") or {}),
                "score": score,
            },
        }
        for doc, score in selected
    ]


def search_relevant_documents(
    conn,
    question: str,
    *,
    embed_model: str,
    source_ids: list[str] | None = None,
    fetch_k: int = 20,
    k: int = 4,
    lambda_: float = 0.1,
    embed_query: Callable[[str], list[float]] | None = None,
) -> list[RetrievedDocument]:
    vector = (embed_query or default_embed_query)(question)
    docs = load_chunks(conn, embed_model, source_ids)
    if docs and len(docs[0]["embedding"]) != len(vector):
        raise RuntimeError(
            "A consulta e o índice têm dimensões diferentes "
            f"({len(vector)} e {len(docs[0]['embedding'])}). "
            "O modelo ativo não é o que gravou esses vetores. Rode o crawl de novo."
        )

    scored: list[tuple[StoredEmbedding, float]] = [
        (doc, cosine_similarity(vector, doc["embedding"])) for doc in docs
    ]
    scored.sort(key=lambda item: item[1], reverse=True)
    scored = scored[:fetch_k]
    return max_marginal_relevance(scored, k, lambda_)
