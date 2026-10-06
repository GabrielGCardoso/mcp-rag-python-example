#!/usr/bin/env python3
"""Indexa as fontes locais de sources.yaml no SQLite."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.indexer import format_reports, index_sources
from lib.sources import load_sources


def _progress(message: str) -> None:
    print(message, flush=True)


def main() -> None:
    sources = [source for source in load_sources() if source["kind"] == "local"]
    if not sources:
        raise SystemExit("Nenhuma fonte local em sources.yaml")
    text, failed = format_reports(index_sources(sources, log=_progress))
    print(text)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
