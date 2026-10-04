#!/usr/bin/env python3
"""Crawl manual: fontes locais e git shallow, reindexando só o que mudou."""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))

from lib.indexer import format_reports, index_sources
from lib.sources import load_sources


def main() -> None:
    text, failed = format_reports(index_sources(load_sources()))
    print(text)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
