import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from lib.config import CODE_CHUNK_CHARS, DATA_DIR, chunk_chars
from lib.embeddings import active_embed_model, embed_texts as default_embed_texts
from lib.sources import iter_files, language_for, source_root, sync_git
from lib.store import (
    connect,
    delete_file,
    get_file,
    list_paths,
    pack_embedding,
    record_source,
    replace_file,
)

BATCH_SIZE = 16


@dataclass(frozen=True)
class IndexReport:
    source_id: str
    indexed_files: int
    skipped_files: int
    removed_files: int
    chunk_count: int
    error: str | None = None


def split_text(path: str, text: str, size: int) -> list[str]:
    language = language_for(path)
    if language == "markdown":
        chunk_size = size
    elif language:
        chunk_size = min(size, CODE_CHUNK_CHARS)
    else:
        chunk_size = min(size, CODE_CHUNK_CHARS)
        language = None

    overlap = min(max(chunk_size // 10, 0), chunk_size - 1)
    if language:
        splitter = RecursiveCharacterTextSplitter.from_language(
            language,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap,
        )
    return [
        chunk.page_content
        for chunk in splitter.create_documents([text])
        if chunk.page_content.strip()
    ]


def index_sources(
    sources: list[dict],
    *,
    embed_texts=default_embed_texts,
    embed_model: str | None = None,
    db_path: Path | None = None,
    data_dir: Path | None = None,
) -> list[IndexReport]:
    model = embed_model or active_embed_model()
    reports: list[IndexReport] = []
    for source in sources:
        reports.append(
            _index_source(
                source,
                embed_texts=embed_texts,
                embed_model=model,
                db_path=db_path,
                data_dir=data_dir,
            )
        )
    return reports


def _index_source(
    source: dict,
    *,
    embed_texts,
    embed_model: str,
    db_path: Path | None,
    data_dir: Path | None,
) -> IndexReport:
    source_id = source["id"]
    indexed = 0
    skipped = 0
    removed = 0
    error: str | None = None
    commit_sha: str | None = None
    crawled_at = datetime.now(timezone.utc).isoformat()

    try:
        root = source_root(source, data_dir if data_dir is not None else DATA_DIR)
        if source["kind"] == "git":
            commit_sha = sync_git(source, root)

        files = iter_files(root, source["include"], source["exclude"])
        seen: set[str] = set()
        size = chunk_chars()

        with connect(db_path) as conn:
            for file in files:
                rel = file.relative_to(root).as_posix()
                seen.add(rel)
                try:
                    payload = file.read_bytes()
                    text = payload.decode("utf-8")
                except UnicodeDecodeError:
                    skipped += 1
                    continue

                digest = hashlib.sha256(payload).hexdigest()
                current = get_file(conn, source_id, rel)
                if (
                    current is not None
                    and current["content_hash"] == digest
                    and current["embed_model"] == embed_model
                ):
                    skipped += 1
                    continue

                parts = split_text(rel, text, size)
                stored: list[tuple[int, str, bytes]] = []
                dim = 0
                if parts:
                    vectors: list[list[float]] = []
                    for start in range(0, len(parts), BATCH_SIZE):
                        batch = parts[start : start + BATCH_SIZE]
                        vectors.extend(embed_texts(batch))
                    if len(vectors) != len(parts):
                        raise RuntimeError(
                            "o embedder devolveu um número diferente de vetores"
                        )
                    dim = len(vectors[0])
                    for index, (part, vector) in enumerate(zip(parts, vectors)):
                        if len(vector) != dim:
                            raise RuntimeError(
                                f"dimensão misturada ao indexar {source_id}:{rel}"
                            )
                        stored.append((index, part, pack_embedding(vector)))

                replace_file(
                    conn,
                    source_id=source_id,
                    path=rel,
                    content_hash=digest,
                    embed_model=embed_model,
                    embed_dim=dim,
                    commit_sha=commit_sha,
                    chunks=stored,
                )
                indexed += 1

            for rel in sorted(list_paths(conn, source_id) - seen):
                delete_file(conn, source_id, rel)
                removed += 1
    except Exception as exc:
        error = str(exc)

    with connect(db_path) as conn:
        count = record_source(
            conn,
            source_id=source_id,
            kind=source["kind"],
            crawled_at=crawled_at,
            commit_sha=commit_sha,
            error=error,
        )

    return IndexReport(
        source_id=source_id,
        indexed_files=indexed,
        skipped_files=skipped,
        removed_files=removed,
        chunk_count=count,
        error=error,
    )


def format_reports(reports: list[IndexReport]) -> tuple[str, bool]:
    lines: list[str] = []
    failed = False
    for report in reports:
        lines.append(
            f"{report.source_id}: indexados={report.indexed_files} "
            f"pulados={report.skipped_files} removidos={report.removed_files} "
            f"chunks={report.chunk_count}"
        )
        if report.error:
            failed = True
            lines.append(f"{report.source_id}: {report.error}")
    return "\n".join(lines), failed
