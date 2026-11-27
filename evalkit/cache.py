"""
Content-addressed disk cache.

This is the component that makes the ablation grid affordable. Twelve configs
over 200 questions is 2,400 pipeline runs and as many judge calls; without a
cache you re-pay all of it every time you fix a bug in the report generator.

Two things get cached, keyed on content rather than on time:

  the FAISS index   keyed by (chunk size, overlap, embedding model), so configs
                    that share those three share one index on disk
  judge verdicts    keyed by (judge prompt, question, answer), so re-scoring an
                    unchanged answer never calls the LLM twice

Cache entries are plain JSON files. They are meant to be inspectable, and
deleting the directory is always safe.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CACHE_DIR = PROJECT_ROOT / "reports" / ".cache"
INDEX_CACHE_DIR = PROJECT_ROOT / "reports" / ".index-cache"


def digest(*parts: str) -> str:
    """Stable digest of any number of string parts."""
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(str(part).encode())
        hasher.update(b"\x00")  # separator, so ("ab","c") != ("a","bc")
    return hasher.hexdigest()[:16]


class JsonCache:
    """A namespaced JSON cache. Misses are cheap; corruption is self-healing."""

    def __init__(self, namespace: str, root: str | Path = CACHE_DIR):
        self.dir = Path(root) / namespace
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str):
        path = self._path(key)
        if not path.exists():
            self.misses += 1
            return None
        try:
            value = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            # A half-written entry from an interrupted run. Drop it and re-compute.
            path.unlink(missing_ok=True)
            self.misses += 1
            return None
        self.hits += 1
        return value

    def set(self, key: str, value) -> None:
        # Write to a temp file then rename, so an interrupted run cannot leave
        # a truncated entry that later reads as valid.
        path = self._path(key)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(value, indent=2, sort_keys=True))
        tmp.replace(path)

    def get_or_compute(self, key: str, compute):
        cached = self.get(key)
        if cached is not None:
            return cached
        value = compute()
        self.set(key, value)
        return value

    @property
    def stats(self) -> dict[str, int]:
        total = self.hits + self.misses
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 3) if total else 0.0,
        }


def index_dir_for(index_hash: str) -> Path:
    """Where the FAISS index for a given chunk/embedding combination lives."""
    path = INDEX_CACHE_DIR / index_hash
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
