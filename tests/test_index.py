import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.embeddings import document_prefix, query_prefix
from lib.indexer import index_sources, split_text
from lib.sources import (
    load_sources,
    matches_any,
    read_source_text,
    redact_secrets,
)
from lib.store import connect, pack_embedding, replace_file, unpack_embedding
from lib.vector_search import search_relevant_documents


def _embed(texts: list[str]) -> list[list[float]]:
    vectors = []
    for text in texts:
        if "alpha" in text:
            vectors.append([1.0, 0.0])
        elif "beta" in text:
            vectors.append([0.0, 1.0])
        else:
            vectors.append([0.2, 0.2])
    return vectors


class IndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "index.sqlite"
        self.data = self.root / "data"
        self.docs = self.root / "docs"
        self.docs.mkdir()
        (self.docs / "alpha.md").write_text("# Alpha\n\nalpha is the topic\n", encoding="utf-8")
        (self.docs / "beta.md").write_text("# Beta\n\nbeta is the other topic\n", encoding="utf-8")
        self.calls = 0

        def counting(texts: list[str]) -> list[list[float]]:
            self.calls += 1
            return _embed(texts)

        self.embed = counting

    def _source(self, source_id: str = "docs", path: Path | None = None) -> dict:
        return {
            "id": source_id,
            "kind": "local",
            "path": path or self.docs,
            "include": ["**/*.md"],
            "exclude": [],
        }

    def _index(self, sources: list[dict] | None = None, model: str = "test-model"):
        return index_sources(
            sources or [self._source()],
            embed_texts=self.embed,
            embed_model=model,
            db_path=self.db,
            data_dir=self.data,
        )

    def test_blob_roundtrip(self) -> None:
        blob = pack_embedding([-1.5, 0.25, 3.0])
        self.assertEqual(unpack_embedding(blob), [-1.5, 0.25, 3.0])

    def test_incremental_skip_update_and_delete(self) -> None:
        first = self._index()[0]
        self.assertIsNone(first.error)
        self.assertEqual(first.indexed_files, 2)
        self.assertGreater(first.chunk_count, 0)
        calls_after_first = self.calls

        second = self._index()[0]
        self.assertEqual(second.indexed_files, 0)
        self.assertEqual(second.skipped_files, 2)
        self.assertEqual(self.calls, calls_after_first)

        (self.docs / "alpha.md").write_text("# Alpha\n\nalpha was edited\n", encoding="utf-8")
        third = self._index()[0]
        self.assertEqual(third.indexed_files, 1)
        self.assertEqual(third.skipped_files, 1)
        self.assertGreater(self.calls, calls_after_first)

        (self.docs / "beta.md").unlink()
        fourth = self._index()[0]
        self.assertEqual(fourth.removed_files, 1)
        with connect(self.db) as conn:
            rows = conn.execute(
                "SELECT path FROM chunks WHERE source_id = ?",
                ("docs",),
            ).fetchall()
        self.assertTrue(rows)
        self.assertTrue(all(row["path"] == "alpha.md" for row in rows))

    def test_search_filters_model_and_source(self) -> None:
        other = self.root / "other"
        other.mkdir()
        (other / "alpha.md").write_text("alpha lives here too\n", encoding="utf-8")
        self._index(
            [
                self._source("docs"),
                self._source("other", other),
            ]
        )
        with connect(self.db) as conn:
            replace_file(
                conn,
                source_id="docs",
                path="gamma.md",
                content_hash="x",
                embed_model="other-model",
                embed_dim=2,
                commit_sha=None,
                chunks=[(0, "gamma secret", pack_embedding([1.0, 0.0]))],
            )
            hits = search_relevant_documents(
                conn,
                "alpha",
                embed_model="test-model",
                embed_query=lambda _: [1.0, 0.0],
                k=4,
            )
            scoped = search_relevant_documents(
                conn,
                "alpha",
                embed_model="test-model",
                source_ids=["other"],
                embed_query=lambda _: [1.0, 0.0],
                k=4,
            )
            empty = search_relevant_documents(
                conn,
                "alpha",
                embed_model="test-model",
                source_ids=[],
                embed_query=lambda _: [1.0, 0.0],
            )
            stale = search_relevant_documents(
                conn,
                "alpha",
                embed_model="missing-model",
                embed_query=lambda _: [1.0, 0.0],
            )

        self.assertTrue(hits)
        self.assertIn("alpha", hits[0]["pageContent"])
        self.assertGreater(hits[0]["metadata"]["score"], 0.9)
        self.assertNotIn("gamma", " ".join(item["pageContent"] for item in hits))
        self.assertTrue(any(item["metadata"]["source_id"] == "docs" for item in hits))
        self.assertTrue(all(item["metadata"]["source_id"] == "other" for item in scoped))
        self.assertEqual(empty, [])
        self.assertEqual(stale, [])

    def test_globs_and_read_range(self) -> None:
        self.assertTrue(matches_any("guide.md", ["**/*.md"]))
        self.assertTrue(matches_any("a/b.md", ["**/*.md"]))
        self.assertTrue(matches_any("README", ["**/README*"]))
        self.assertTrue(matches_any("docs/README.md", ["**/README*"]))
        self.assertTrue(matches_any("package-lock.json", ["**/*lock*"]))
        self.assertFalse(matches_any("guide.md", ["**/*lock*"]))
        self.assertTrue(split_text("app.ts", "export const n = 1;\nfunction f(){ return 1 }\n", 400))

        nested = self.docs / "pkg"
        nested.mkdir()
        (nested / "note.md").write_text("line1\nline2\nline3\n", encoding="utf-8")
        (nested / "package-lock.json").write_text("{}\n", encoding="utf-8")
        source = {
            "id": "docs",
            "kind": "local",
            "path": self.docs,
            "include": ["**/*"],
            "exclude": ["**/*lock*"],
        }
        report = self._index([source])[0]
        self.assertIsNone(report.error)
        with connect(self.db) as conn:
            paths = {
                row["path"]
                for row in conn.execute("SELECT path FROM files").fetchall()
            }
        self.assertIn("pkg/note.md", paths)
        self.assertNotIn("pkg/package-lock.json", paths)

        text = read_source_text(
            "docs",
            "pkg/note.md",
            start_line=2,
            end_line=2,
            sources=[source],
        )
        self.assertEqual(text, "line2")
        with self.assertRaises(ValueError):
            read_source_text(
                "docs",
                "../alpha.md",
                sources=[source],
            )

    def test_git_source_reindexes_when_head_changes(self) -> None:
        origin = self.root / "origin"
        self._git(origin, "git", "init", "-b", "main", os.fspath(origin))
        self._git(origin, "git", "-C", os.fspath(origin), "config", "user.email", "t@example.com")
        self._git(origin, "git", "-C", os.fspath(origin), "config", "user.name", "Test")
        (origin / "README.md").write_text("# Alpha\n\nalpha in git\n", encoding="utf-8")
        self._git(origin, "git", "-C", os.fspath(origin), "add", "README.md")
        self._git(
            origin,
            "git",
            "-C",
            os.fspath(origin),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "one",
        )

        source = {
            "id": "repo",
            "kind": "git",
            "url": os.fspath(origin),
            "branch": "main",
            "include": ["**/*.md"],
            "exclude": [],
        }
        first = self._index([source])[0]
        self.assertIsNone(first.error, first.error)
        self.assertEqual(first.indexed_files, 1)
        with connect(self.db) as conn:
            commit = conn.execute(
                "SELECT last_commit FROM sources WHERE id = ?",
                ("repo",),
            ).fetchone()["last_commit"]
        self.assertEqual(len(commit), 40)

        (origin / "README.md").write_text("# Alpha\n\nalpha edited in git\n", encoding="utf-8")
        self._git(origin, "git", "-C", os.fspath(origin), "add", "README.md")
        self._git(
            origin,
            "git",
            "-C",
            os.fspath(origin),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "two",
        )
        second = self._index([source])[0]
        self.assertIsNone(second.error, second.error)
        self.assertEqual(second.indexed_files, 1)
        with connect(self.db) as conn:
            text = conn.execute(
                "SELECT text FROM chunks WHERE source_id = ?",
                ("repo",),
            ).fetchone()["text"]
            new_commit = conn.execute(
                "SELECT last_commit FROM sources WHERE id = ?",
                ("repo",),
            ).fetchone()["last_commit"]
        self.assertIn("edited", text)
        self.assertNotEqual(new_commit, commit)

    def test_prefixes_and_secret_redaction(self) -> None:
        self.assertEqual(document_prefix("nomic-embed-text"), "search_document: ")
        self.assertEqual(query_prefix("nomic-embed-text"), "search_query: ")
        self.assertTrue(query_prefix("qwen3-embedding:0.6b").startswith("Instruct:"))
        self.assertEqual(document_prefix("qwen3-embedding:0.6b"), "")
        self.assertIn(
            "//***@",
            redact_secrets("fatal: https://user:token@github.com/org/repo.git"),
        )

    def test_sources_yaml_rejects_bad_id(self) -> None:
        path = self.root / "sources.yaml"
        path.write_text(
            "sources:\n  - id: '../x'\n    kind: local\n    path: .\n    include: ['**/*.md']\n",
            encoding="utf-8",
        )
        with self.assertRaises(SystemExit):
            load_sources(path)

    def _git(self, origin: Path, *args: str) -> None:
        subprocess.run(args, check=True, cwd=origin if origin.exists() else None, capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
