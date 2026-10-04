import json

import httpx

from lib.config import (
    EMBED_NUM_CTX,
    OLLAMA_BASE_URL,
    OLLAMA_CHAT_MODEL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_PREDICT,
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


def chat(prompt: str) -> str:
    options: dict = {"num_gpu": 0}
    if OLLAMA_NUM_CTX is not None:
        options["num_ctx"] = OLLAMA_NUM_CTX
    if OLLAMA_NUM_PREDICT is not None:
        options["num_predict"] = OLLAMA_NUM_PREDICT

    with httpx.stream(
        "POST",
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_CHAT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": options,
        },
        timeout=600.0,
    ) as response:
        if not response.is_success:
            raise RuntimeError(
                f"Ollama chat failed ({response.status_code}): {response.read().decode()}"
            )

        parts: list[str] = []
        buffer = ""

        for chunk in response.iter_bytes():
            buffer += chunk.decode()
            lines = buffer.split("\n")
            buffer = lines.pop() or ""

            for line in lines:
                if not line.strip():
                    continue
                data = json.loads(line)
                text = data.get("message", {}).get("content")
                if text:
                    parts.append(text)

        if buffer.strip():
            data = json.loads(buffer)
            text = data.get("message", {}).get("content")
            if text:
                parts.append(text)

    return "".join(parts)
