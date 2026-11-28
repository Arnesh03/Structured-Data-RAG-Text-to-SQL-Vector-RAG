"""
The golden set: loading, validation and slicing.

This file is the smallest part of the harness and by far the most valuable
thing in it. The code here is replaceable; a few hundred hand-reviewed
questions over your own corpus are not.

Validation is strict on purpose. A malformed record fails the load rather than
quietly scoring as a miss, because a dataset that silently degrades produces
numbers that look fine and mean nothing.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Literal

from pydantic import BaseModel, Field, model_validator

EVALKIT_ROOT = Path(__file__).parent
GOLDEN_DIR = EVALKIT_ROOT / "golden"
GOLDEN_SET = GOLDEN_DIR / "golden_set.jsonl"

Route = Literal["sql", "rag"]

# The policy corpus. Retrieval ground truth is expressed in these filenames.
#
# Imported from `corpus` rather than restated, so adding a document to the real
# corpus cannot leave the validator rejecting questions about it. `corpus` pulls
# in only `config`, so this stays importable without LangChain.
from corpus import REAL_DOCUMENTS  # noqa: E402

GENERATED_SOURCES = {
    "admission_policy.pdf",
    "insurance_billing_policy.pdf",
    "clinical_guidelines.pdf",
    "discharge_policy.pdf",
    "patient_faq.pdf",
}

KNOWN_SOURCES = GENERATED_SOURCES | set(REAL_DOCUMENTS)


class GoldenRecord(BaseModel):
    """One labeled question."""

    id: str
    question: str
    route_label: Route
    category: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"

    # Ground truth. Which of these is required depends on the route; see below.
    gold_sql: str | None = None
    gold_answer: str | None = None
    gold_doc_ids: list[str] | None = None

    answerable: bool = True
    notes: str = ""

    @model_validator(mode="after")
    def _check_ground_truth(self) -> "GoldenRecord":
        if not self.answerable:
            # Unanswerable questions carry no ground truth by definition: the
            # only correct behaviour is to decline.
            return self

        if self.route_label == "sql" and not self.gold_sql:
            raise ValueError(f"{self.id}: answerable sql question needs gold_sql")

        if self.route_label == "rag":
            if not self.gold_doc_ids:
                raise ValueError(f"{self.id}: answerable rag question needs gold_doc_ids")
            unknown = sorted(set(self.gold_doc_ids) - KNOWN_SOURCES)
            if unknown:
                raise ValueError(f"{self.id}: unknown source document(s) {unknown}")

        return self


class GoldenSet:
    """An ordered collection of records, with slicing for CI and debugging."""

    def __init__(self, records: list[GoldenRecord]):
        ids = [r.id for r in records]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"duplicate question ids: {duplicates}")
        self.records = records

    # ── Loading ───────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: str | Path = GOLDEN_SET) -> "GoldenSet":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run `make eval-seed` to generate candidates, "
                "then review them by hand before scoring anything."
            )

        records, errors = [], []
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                records.append(GoldenRecord(**json.loads(line)))
            except Exception as exc:  # noqa: BLE001 - collect every problem at once
                errors.append(f"  line {lineno}: {exc}")

        if errors:
            raise ValueError(f"{path} has {len(errors)} invalid record(s):\n" + "\n".join(errors))

        return cls(records)

    # ── Slicing ───────────────────────────────────────────────────────

    def filter(self, **criteria) -> "GoldenSet":
        """Narrow by any field, e.g. `filter(route_label='sql')`."""
        kept = [
            r for r in self.records
            if all(getattr(r, key, None) == value for key, value in criteria.items())
        ]
        return GoldenSet(kept)

    def stratified_sample(self, n: int, seed: int = 0) -> "GoldenSet":
        """
        Take `n` records spread across categories, not the first `n` rows.

        CI runs this. A subset that is all easy SQL questions gates nothing.
        """
        import random

        buckets: dict[str, list[GoldenRecord]] = {}
        for record in self.records:
            buckets.setdefault(record.category, []).append(record)

        rng = random.Random(seed)
        for bucket in buckets.values():
            rng.shuffle(bucket)

        picked, exhausted = [], False
        while len(picked) < n and not exhausted:
            exhausted = True
            for bucket in sorted(buckets):
                if buckets[bucket] and len(picked) < n:
                    picked.append(buckets[bucket].pop())
                    exhausted = False

        picked.sort(key=lambda r: r.id)
        return GoldenSet(picked)

    # ── Reporting ─────────────────────────────────────────────────────

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.records),
            "sql": len(self.filter(route_label="sql").records),
            "rag": len(self.filter(route_label="rag").records),
            "unanswerable": len([r for r in self.records if not r.answerable]),
            "categories": len({r.category for r in self.records}),
        }

    def __len__(self) -> int:
        return len(self.records)

    def __iter__(self) -> Iterator[GoldenRecord]:
        return iter(self.records)
