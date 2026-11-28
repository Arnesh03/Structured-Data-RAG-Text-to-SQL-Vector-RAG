"""
Generates CANDIDATE questions for you to review. It does not generate a dataset.

The distinction matters. Questions generated from the same chunks your
retriever indexes will flatter your retriever, and gold answers no human
checked are not ground truth. So this writes `candidates.jsonl` with
`reviewed: false` on every row, and `promote` refuses to move a row into the
golden set until you have set that to true.

Expect to reject roughly a third: leaky questions that restate their chunk,
trivially easy ones, and SQL whose gold query returns nothing. Record the keep
rate and the reasons; "I rejected 32% for answer leakage" shows judgement.

  make eval-seed       generate candidates
  (review by hand)     edit candidates.jsonl, set reviewed: true
  make eval-promote    merge the reviewed rows into the golden set
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

from evalkit.dataset import GOLDEN_SET, GoldenSet

GOLDEN_DIR = Path(__file__).parent / "golden"
CANDIDATES = GOLDEN_DIR / "candidates.jsonl"

RAG_PROMPT = """\
Here is one excerpt from a hospital policy document.

---
{chunk}
---

Write {n} questions a patient or member of staff would realistically ask, that
this excerpt alone answers.

Rules:
- Do NOT reuse the excerpt's wording. Someone who had not read it should still
  ask the question in these words.
- No question may quote a number or phrase verbatim from the excerpt.
- Vary the difficulty: at least one should need two sentences of the excerpt.

Respond with ONLY a JSON array of strings.
"""

SQL_PROMPT = """\
A SQLite table named `admissions` has these columns:

{schema}

Write {n} analytical questions a hospital administrator would ask of this
table, each with the SQL that answers it.

Rules:
- Use only the columns listed. Invent no columns.
- Vary the shape: aggregates, filters, group-bys, rankings, time windows, ratios.
- Every query must return at least one row against a realistically populated table.
- Use the materialized columns (admission_year, admission_month, age_group,
  length_of_stay_days, billing_per_day) rather than recomputing them.

Respond with ONLY a JSON array of objects: {{"question": "...", "sql": "..."}}
"""


def _parse_json_array(raw: str):
    import re
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return []


def _ask(prompt: str) -> str:
    from llm import get_llm
    response = get_llm(temperature=0.7).invoke(prompt)
    return getattr(response, "content", str(response))


def seed_rag(count: int, per_chunk: int = 3) -> list[dict]:
    """Generate candidates from sampled policy chunks."""
    from vectorstore import load_policy_documents
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from config import CHUNK_OVERLAP, CHUNK_SIZE

    docs = load_policy_documents()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    rng = random.Random(0)
    rng.shuffle(chunks)

    out: list[dict] = []
    for chunk in chunks:
        if len(out) >= count:
            break
        source = chunk.metadata.get("source")
        try:
            questions = _parse_json_array(
                _ask(RAG_PROMPT.format(chunk=chunk.page_content.strip(), n=per_chunk))
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  generation failed: {exc}", file=sys.stderr)
            continue

        for question in questions:
            if not isinstance(question, str) or len(out) >= count:
                continue
            out.append({
                "id": f"cand_rag_{len(out):04d}",
                "question": question.strip(),
                "route_label": "rag",
                "category": "generated_rag",
                "difficulty": "medium",
                "gold_sql": None,
                "gold_answer": None,
                "gold_doc_ids": [source],
                "answerable": True,
                "notes": "",
                "reviewed": False,
                "source_chunk": chunk.page_content.strip()[:400],
            })
        print(f"  {len(out)}/{count} rag candidates")
    return out


def seed_sql(count: int, batch: int = 10) -> list[dict]:
    """Generate candidates from the schema, keeping only queries that execute."""
    from config import DB_PATH
    from database import CREATE_TABLE_SQL

    conn = sqlite3.connect(DB_PATH)
    out: list[dict] = []
    rejected = 0

    while len(out) < count:
        try:
            items = _parse_json_array(
                _ask(SQL_PROMPT.format(schema=CREATE_TABLE_SQL, n=batch))
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  generation failed: {exc}", file=sys.stderr)
            break
        if not items:
            break

        for item in items:
            if len(out) >= count:
                break
            question, gold = item.get("question"), item.get("sql")
            if not question or not gold:
                rejected += 1
                continue

            # Execute now. A gold query that errors or returns nothing is not
            # ground truth, and finding that out later corrupts a whole run.
            try:
                rows = conn.execute(gold).fetchall()
            except Exception:  # noqa: BLE001
                rejected += 1
                continue
            if not rows:
                rejected += 1
                continue

            out.append({
                "id": f"cand_sql_{len(out):04d}",
                "question": question.strip(),
                "route_label": "sql",
                "category": "generated_sql",
                "difficulty": "medium",
                "gold_sql": gold.strip(),
                "gold_answer": None,
                "gold_doc_ids": None,
                "answerable": True,
                "notes": "",
                "reviewed": False,
            })
        print(f"  {len(out)}/{count} sql candidates ({rejected} auto-rejected)")

    print(f"  auto-rejected {rejected} sql candidates that errored or returned nothing")
    return out


def promote() -> None:
    """Move reviewed candidates into the golden set."""
    if not CANDIDATES.exists():
        raise SystemExit(f"{CANDIDATES} not found. Run `make eval-seed` first.")

    rows = [json.loads(line) for line in CANDIDATES.read_text().splitlines() if line.strip()]
    reviewed = [r for r in rows if r.get("reviewed") is True]
    if not reviewed:
        raise SystemExit(
            f"None of the {len(rows)} candidates are marked reviewed.\n"
            "Read each one, fix or delete it, then set \"reviewed\": true."
        )

    existing = GoldenSet.load(GOLDEN_SET).records if GOLDEN_SET.exists() else []
    known = {r.id for r in existing}

    added = []
    for row in reviewed:
        row.pop("reviewed", None)
        row.pop("source_chunk", None)
        if row["id"] in known:
            continue
        added.append(row)

    with GOLDEN_SET.open("a") as handle:
        for row in added:
            handle.write(json.dumps(row) + "\n")

    keep_rate = len(reviewed) / len(rows) if rows else 0
    print(f"promoted {len(added)} of {len(rows)} candidates (keep rate {keep_rate:.0%})")
    print(f"golden set now holds {len(GoldenSet.load(GOLDEN_SET))} questions")
    print("Record that keep rate and your rejection reasons in the README.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate candidate questions for review.")
    parser.add_argument("--rag", type=int, default=60)
    parser.add_argument("--sql", type=int, default=60)
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    if args.promote:
        promote()
        return 0

    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    candidates = []
    if args.sql:
        print(f"Generating {args.sql} sql candidates...")
        candidates += seed_sql(args.sql)
    if args.rag:
        print(f"Generating {args.rag} rag candidates...")
        candidates += seed_rag(args.rag)

    CANDIDATES.write_text("\n".join(json.dumps(c) for c in candidates) + "\n")
    print(f"\nwrote {len(candidates)} candidates to {CANDIDATES}")
    print("NOW REVIEW THEM BY HAND. Budget four hours; it is the work that")
    print("makes this dataset yours. Then: make eval-promote")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
