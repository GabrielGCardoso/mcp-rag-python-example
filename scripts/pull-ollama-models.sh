#!/usr/bin/env bash
set -euo pipefail

EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
CHAT_MODEL="${OLLAMA_CHAT_MODEL:-llama3.2:3b}"

echo "Pulling embedding model: ${EMBED_MODEL}"
docker compose exec ollama ollama pull "${EMBED_MODEL}"

echo "Pulling chat model: ${CHAT_MODEL}"
docker compose exec ollama ollama pull "${CHAT_MODEL}"

echo "Done."
