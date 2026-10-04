import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent


def _path_env(name: str, default: str) -> Path:
    raw = os.environ.get(name, default).strip() or default
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def _optional_int(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} precisa ser um inteiro, recebeu {raw!r}") from exc
    if value <= 0:
        raise RuntimeError(f"{name} precisa ser maior que zero, recebeu {value}")
    return value


EMBED_BACKEND = os.environ.get("EMBED_BACKEND", "local").strip().lower() or "local"
LOCAL_EMBED_MODEL = os.environ.get(
    "LOCAL_EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
).strip()
SQLITE_PATH = _path_env("SQLITE_PATH", "data/index.sqlite")
SOURCES_FILE = _path_env("SOURCES_FILE", "sources.yaml")
DATA_DIR = _path_env("DATA_DIR", "data")

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text").strip()
OLLAMA_CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "").strip()

EMBED_NUM_CTX = _optional_int("EMBED_NUM_CTX")
OLLAMA_NUM_CTX = _optional_int("OLLAMA_NUM_CTX")
OLLAMA_NUM_PREDICT = _optional_int("OLLAMA_NUM_PREDICT")

DEFAULT_CHUNK_CHARS = 500
CODE_CHUNK_CHARS = 400


def chunk_chars() -> int:
    if EMBED_NUM_CTX is None:
        return DEFAULT_CHUNK_CHARS
    return max(EMBED_NUM_CTX * 4, 32)


def chat_enabled() -> bool:
    return bool(OLLAMA_CHAT_MODEL)
