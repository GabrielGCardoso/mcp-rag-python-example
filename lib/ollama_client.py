import json

import httpx

from lib.config import OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, OLLAMA_EMBED_MODEL


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/embed",
        json={"model": OLLAMA_EMBED_MODEL, "input": texts},
        timeout=300.0,
    )

    if not response.is_success:
        raise RuntimeError(
            f"Ollama embed failed ({response.status_code}): {response.text}. "
            f"Run: docker compose exec ollama ollama pull {OLLAMA_EMBED_MODEL}"
        )

    data = response.json()
    embeddings = data.get("embeddings")
    if embeddings:
        return embeddings

    embedding = data.get("embedding")
    if embedding:
        return [embedding]

    raise RuntimeError("Ollama embed response missing embeddings")


def embed_query(text: str) -> list[float]:
    return embed_texts([text])[0]


def chat(prompt: str) -> str:
    with httpx.stream(
        "POST",
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": OLLAMA_CHAT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": {"num_gpu": 0},
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
