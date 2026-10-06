import httpx

from lib.config import (
    EMBED_NUM_CTX,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    body: dict = {"model": OLLAMA_EMBED_MODEL, "input": texts}
    if EMBED_NUM_CTX is not None:
        body["options"] = {"num_ctx": EMBED_NUM_CTX}

    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json=body,
        timeout=300.0,
    )

    if not response.is_success:
        raise RuntimeError(
            f"Ollama embed failed ({response.status_code}): {response.text}. "
            f"Confira se o Ollama em {OLLAMA_BASE_URL} tem o modelo {OLLAMA_EMBED_MODEL}."
        )

    data = response.json()
    embeddings = data.get("embeddings")
    if embeddings:
        return embeddings

    embedding = data.get("embedding")
    if embedding:
        return [embedding]

    raise RuntimeError("Ollama embed response missing embeddings")
