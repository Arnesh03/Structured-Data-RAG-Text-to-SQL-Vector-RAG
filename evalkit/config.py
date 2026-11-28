"""
Experiment configuration.

A config is a named set of overrides for the environment variables `config.py`
already reads. That is the whole trick: the pipeline needs no refactor to be
made tunable, because it is tunable already.

Every config hashes to a short `config_hash` that stamps each result row, so a
number in a report can always be traced back to the exact settings that
produced it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

EVALKIT_ROOT = Path(__file__).parent
PROJECT_ROOT = EVALKIT_ROOT.parent
CONFIGS_DIR = PROJECT_ROOT / "configs"

# Environment variables `config.py` reads that change pipeline behaviour.
# Anything outside this set is rejected, so a typo fails loudly instead of
# silently evaluating the baseline twice under two different names.
TUNABLE = (
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "RETRIEVER_TOP_K",
    "EMBEDDING_MODEL",
    "LLM_PROVIDER",
    "LLM_TEMPERATURE",
    "SQL_MAX_ROWS",
    "GROQ_MODEL",
    "OPENAI_MODEL",
)

# Changing any of these invalidates the FAISS index, so the worker rebuilds it
# into a directory keyed by their values.
#
# The corpus itself is keyed in too (see `index_hash`). Settings alone are not
# enough: the same chunk size over a different set of documents is a different
# index, and reusing one silently would make a corpus change look like it had
# no effect at all.
INDEX_KEYS = ("CHUNK_SIZE", "CHUNK_OVERLAP", "EMBEDDING_MODEL")


class ConfigError(ValueError):
    """Raised when a config file names a setting the pipeline does not read."""


@dataclass(frozen=True)
class EvalConfig:
    """One point in the experiment space."""

    name: str
    settings: tuple[tuple[str, str], ...]
    notes: str = ""

    # ── Construction ──────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, raw: dict) -> "EvalConfig":
        data = dict(raw)
        name = str(data.pop("name", "unnamed"))
        notes = str(data.pop("notes", ""))

        unknown = sorted(set(data) - set(TUNABLE))
        if unknown:
            raise ConfigError(
                f"config {name!r} sets {unknown}, which the pipeline does not read. "
                f"Known settings: {', '.join(TUNABLE)}"
            )

        # Normalize to strings now so the hash cannot drift on 4 vs "4".
        settings = tuple(sorted((k, str(v)) for k, v in data.items()))
        return cls(name=name, settings=settings, notes=notes)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "EvalConfig":
        path = Path(path)
        raw = yaml.safe_load(path.read_text()) or {}
        raw.setdefault("name", path.stem)
        return cls.from_dict(raw)

    # ── Identity ──────────────────────────────────────────────────────

    @property
    def as_dict(self) -> dict[str, str]:
        return dict(self.settings)

    @property
    def config_hash(self) -> str:
        """Stable 12-character digest of the settings, ignoring name and notes."""
        payload = json.dumps(self.as_dict, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    @property
    def index_hash(self) -> str:
        """Digest of the settings that invalidate the FAISS index, plus the corpus."""
        from corpus import fingerprint

        subset = {k: v for k, v in self.settings if k in INDEX_KEYS}
        subset["__corpus__"] = fingerprint()
        payload = json.dumps(subset, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    def env(self) -> dict[str, str]:
        """The environment overrides this config applies to a worker process."""
        return self.as_dict


def load_all(directory: str | Path = None) -> list[EvalConfig]:
    """Load every YAML config under `configs/`, baseline first."""
    directory = Path(directory or CONFIGS_DIR)
    paths = sorted(directory.rglob("*.yaml"))
    configs = [EvalConfig.from_yaml(p) for p in paths]
    configs.sort(key=lambda c: (c.name != "baseline", c.name))
    return configs
