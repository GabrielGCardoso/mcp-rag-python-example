#!/usr/bin/env bash
set -euo pipefail

EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"
CHAT_MODEL="${OLLAMA_CHAT_MODEL:-}"

echo "Pulling embedding model: ${EMBED_MODEL}"
docker compose exec ollama ollama pull "${EMBED_MODEL}"

if [[ -n "${CHAT_MODEL}" ]]; then
  echo "Pulling chat model: ${CHAT_MODEL}"
  docker compose exec ollama ollama pull "${CHAT_MODEL}"
fi

echo "Done."
