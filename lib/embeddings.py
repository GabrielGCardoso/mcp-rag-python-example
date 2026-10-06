import threading

from lib.config import EMBED_BACKEND, LOCAL_EMBED_MODEL, OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL
from lib.ollama_client import embed_texts as ollama_embed_texts

_NOMIC_DOC = "search_document: "
_NOMIC_QUERY = "search_query: "
_QWEN_QUERY = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\n"
    "Query: "
)

_local_model = None
_local_lock = threading.Lock()


def describe_embed_backend() -> str:
    model = active_embed_model()
    if EMBED_BACKEND == "ollama":
        return f"usando ollama em {OLLAMA_BASE_URL}, modelo {model}"
    return f"usando embedder local, modelo {model}"


def active_embed_model() -> str:
    if EMBED_BACKEND == "ollama":
        if not OLLAMA_EMBED_MODEL:
            raise RuntimeError("OLLAMA_EMBED_MODEL vazio")
        return OLLAMA_EMBED_MODEL
    if EMBED_BACKEND == "local":
        if not LOCAL_EMBED_MODEL:
            raise RuntimeError("LOCAL_EMBED_MODEL vazio")
        return LOCAL_EMBED_MODEL
    raise RuntimeError(
        f"EMBED_BACKEND desconhecido: {EMBED_BACKEND}. Use local ou ollama."
    )


def document_prefix(model: str) -> str:
    if "nomic-embed" in model:
        return _NOMIC_DOC
    return ""


def query_prefix(model: str) -> str:
    if "nomic-embed" in model:
        return _NOMIC_QUERY
    if "qwen3-embedding" in model:
        return _QWEN_QUERY
    return ""


def _apply_prefix(text: str, prefix: str) -> str:
    if not prefix or text.startswith(prefix):
        return text
    return prefix + text


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if EMBED_BACKEND == "ollama":
        prefix = document_prefix(OLLAMA_EMBED_MODEL)
        prepared = [_apply_prefix(text, prefix) for text in texts]
        return ollama_embed_texts(prepared)
    return _local_vectors(texts, query=False)


def embed_query(text: str) -> list[float]:
    if EMBED_BACKEND == "ollama":
        prefix = query_prefix(OLLAMA_EMBED_MODEL)
        return ollama_embed_texts([_apply_prefix(text, prefix)])[0]
    return _local_vectors([text], query=True)[0]


def _as_floats(vector: object) -> list[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(item) for item in vector]


def _local_model_instance():
    global _local_model
    with _local_lock:
        if _local_model is None:
            try:
                from fastembed import TextEmbedding
            except ImportError as exc:
                raise RuntimeError(
                    "EMBED_BACKEND=local precisa do pacote fastembed. "
                    "Rode pip install -r requirements.txt, ou use EMBED_BACKEND=ollama."
                ) from exc
            _local_model = TextEmbedding(model_name=LOCAL_EMBED_MODEL)
        return _local_model


def _local_vectors(texts: list[str], *, query: bool) -> list[list[float]]:
    model = _local_model_instance()
    prepared = texts
    if "e5" in LOCAL_EMBED_MODEL:
        prefix = "query: " if query else "passage: "
        prepared = [_apply_prefix(text, prefix) for text in texts]
    with _local_lock:
        if query:
            vectors = model.query_embed(prepared)
        else:
            vectors = model.passage_embed(prepared)
        return [_as_floats(vector) for vector in vectors]
