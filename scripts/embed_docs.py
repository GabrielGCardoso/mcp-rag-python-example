#!/usr/bin/env python3
"""Index markdown docs from DOCS_DIR into MongoDB with Ollama embeddings."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from langchain_text_splitters import RecursiveCharacterTextSplitter

from lib.config import DOCS_DIR
from lib.mongodb import get_collection
from lib.ollama_client import embed_texts

BATCH_SIZE = 16


def main() -> None:
    docs_dir = Path(DOCS_DIR)
    if not docs_dir.is_dir():
        raise SystemExit(f"DOCS_DIR not found: {docs_dir}")

    collection = get_collection()
    collection.delete_many({})

    splitter = RecursiveCharacterTextSplitter.from_language(
        "markdown",
        chunk_size=500,
        chunk_overlap=50,
    )

    file_names = sorted(
        p.name for p in docs_dir.iterdir() if p.is_file() and p.suffix == ".md"
    )
    print(file_names)

    for file_name in file_names:
        document = (docs_dir / file_name).read_text(encoding="utf-8")
        print(f"Vectorizing {file_name}")

        chunks = splitter.create_documents([document])
        texts = [chunk.page_content for chunk in chunks]

        for i in range(0, len(texts), BATCH_SIZE):
            batch_texts = texts[i : i + BATCH_SIZE]
            batch_chunks = chunks[i : i + BATCH_SIZE]
            embeddings = embed_texts(batch_texts)

            docs = [
                {
                    "text": chunk.page_content,
                    "embedding": embeddings[j],
                    "metadata": {
                        **(chunk.metadata or {}),
                        "source": file_name,
                    },
                }
                for j, chunk in enumerate(batch_chunks)
            ]

            if docs:
                collection.insert_many(docs)

    print("Done: embeddings indexed.")


if __name__ == "__main__":
    main()
