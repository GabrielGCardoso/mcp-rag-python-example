#!/usr/bin/env bash
set -euo pipefail

EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text}"

echo "Pulling embedding model: ${EMBED_MODEL}"
docker compose exec ollama ollama pull "${EMBED_MODEL}"

echo "Done."
