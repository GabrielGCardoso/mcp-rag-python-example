import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.2:3b")

_root = Path(__file__).resolve().parent.parent
_docs_env = os.environ.get("DOCS_DIR", "fcc_docs")
_docs_path = Path(_docs_env)
DOCS_DIR = _docs_path if _docs_path.is_absolute() else _root / _docs_env

DB_NAME = "docs"
COLLECTION_NAME = "embeddings"
