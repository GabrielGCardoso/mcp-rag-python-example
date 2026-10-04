import fnmatch
import os
import re
import subprocess
from pathlib import Path

import yaml

from lib.config import DATA_DIR, ROOT, SOURCES_FILE

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_SECRET = re.compile(r"//[^/\s:]+:[^/\s@]+@")
_SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "__pycache__", ".venv"}

_LANG = {
    ".py": "python",
    ".js": "js",
    ".jsx": "js",
    ".ts": "ts",
    ".tsx": "ts",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
}


def redact_secrets(text: str) -> str:
    return _SECRET.sub("//***@", text)


def load_sources(path: Path | None = None) -> list[dict]:
    file = Path(path) if path is not None else SOURCES_FILE
    if not file.is_file():
        raise SystemExit(f"sources.yaml não encontrado: {file}")

    raw = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    items = raw.get("sources")
    if not isinstance(items, list) or not items:
        raise SystemExit(f"sources.yaml sem a lista sources: {file}")

    sources: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise SystemExit("cada fonte em sources.yaml precisa ser um mapa")
        source_id = str(item.get("id", "")).strip()
        if not _ID.match(source_id):
            raise SystemExit(f"id de fonte inválido: {source_id!r}")
        if source_id in seen:
            raise SystemExit(f"id de fonte repetido: {source_id}")
        seen.add(source_id)

        kind = str(item.get("kind", "")).strip()
        include = item.get("include")
        if kind not in {"local", "git"}:
            raise SystemExit(f"fonte {source_id}: kind precisa ser local ou git")
        if not isinstance(include, list) or not include:
            raise SystemExit(f"fonte {source_id}: include precisa ser uma lista de globs")

        source = {
            "id": source_id,
            "kind": kind,
            "include": [str(pattern) for pattern in include],
            "exclude": [str(pattern) for pattern in item.get("exclude") or []],
        }
        if kind == "local":
            raw_path = str(item.get("path", "")).strip()
            if not raw_path:
                raise SystemExit(f"fonte {source_id}: path vazio")
            location = Path(raw_path)
            source["path"] = location if location.is_absolute() else ROOT / location
        else:
            url = str(item.get("url", "")).strip()
            if not url:
                raise SystemExit(f"fonte {source_id}: url vazia")
            source["url"] = url
            source["branch"] = str(item.get("branch") or "main").strip() or "main"
        sources.append(source)
    return sources


def matches_any(rel: str, patterns: list[str]) -> bool:
    rel = rel.replace("\\", "/")
    return any(_matches_one(rel, pattern) for pattern in patterns)


def _matches_one(rel: str, pattern: str) -> bool:
    pattern = pattern.replace("\\", "/")
    if fnmatch.fnmatchcase(rel, pattern):
        return True
    if pattern.startswith("**/"):
        return fnmatch.fnmatchcase(rel, pattern[3:])
    return False


def source_root(source: dict, data_dir: Path | None = None) -> Path:
    if source["kind"] == "local":
        return Path(source["path"])
    base = Path(data_dir) if data_dir is not None else DATA_DIR
    return base / "sources" / source["id"]


def iter_files(root: Path, include: list[str], exclude: list[str]) -> list[Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"diretório da fonte não encontrado: {root}")

    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in _SKIP_DIRS]
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            if not matches_any(rel, include):
                continue
            if exclude and matches_any(rel, exclude):
                continue
            found.append(full)
    found.sort()
    return found


def language_for(path: str) -> str | None:
    name = Path(path).name.lower()
    suffix = Path(path).suffix.lower()
    if suffix in {".md", ".mdx", ".markdown"} or name.startswith("readme"):
        return "markdown"
    return _LANG.get(suffix)


def resolve_source_file(root: Path, rel: str) -> Path:
    if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
        raise ValueError("path fora da fonte")
    full = (root / rel).resolve()
    if not full.is_relative_to(root.resolve()):
        raise ValueError("path fora da fonte")
    if not full.is_file():
        raise FileNotFoundError(rel)
    return full


def read_source_text(
    source_id: str,
    path: str,
    *,
    start_line: int | None = None,
    end_line: int | None = None,
    sources: list[dict] | None = None,
    data_dir: Path | None = None,
) -> str:
    chosen = sources if sources is not None else load_sources()
    source = next((item for item in chosen if item["id"] == source_id), None)
    if source is None:
        raise ValueError(f"fonte desconhecida: {source_id}")

    root = source_root(source, data_dir)
    if not root.is_dir():
        raise FileNotFoundError(
            f"{source_id} ainda não está no disco. Rode scripts/crawl.py."
        )

    file = resolve_source_file(root, path)
    text = file.read_text(encoding="utf-8")
    if start_line is None and end_line is None:
        return text

    lines = text.splitlines()
    start = 1 if start_line is None else max(int(start_line), 1)
    end = len(lines) if end_line is None else max(int(end_line), start)
    return "\n".join(lines[start - 1 : end])


def sync_git(source: dict, dest: Path) -> str:
    branch = source["branch"]
    url = source["url"]
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not (dest / ".git").exists():
        if dest.exists():
            raise RuntimeError(f"diretório da fonte existe sem git: {dest}")
        _git(
            ["git", "clone", "--depth", "1", "--branch", branch, url, os.fspath(dest)]
        )
    else:
        _git(["git", "-C", os.fspath(dest), "fetch", "--depth", "1", "origin", branch])
        _git(["git", "-C", os.fspath(dest), "reset", "--hard", f"origin/{branch}"])

    return _git(["git", "-C", os.fspath(dest), "rev-parse", "HEAD"])


def _git(args: list[str]) -> str:
    try:
        proc = subprocess.run(args, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = redact_secrets((exc.stderr or exc.stdout or "").strip())
        raise RuntimeError(detail or "git falhou") from exc
    except FileNotFoundError as exc:
        raise RuntimeError("git não está instalado") from exc
    return proc.stdout.strip()
