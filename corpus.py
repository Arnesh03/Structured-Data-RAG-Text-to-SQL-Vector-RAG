"""
The real policy corpus: public-domain documents, fetched rather than vendored.

The five generated policy PDFs make a tidy demo, but a 37-chunk index is not a
retrieval problem — top-4 returns 11% of the entire corpus, so precision@k
looks excellent and measures nothing. These documents are real, long, and
written by someone else, which is what makes the retrieval metrics mean
something.

They are downloaded, never committed: `data/` is gitignored, and a repository
is not a document store. Run `make corpus` to fetch them.

Sources are works of the U.S. federal government, which are not subject to
copyright under 17 U.S.C. 105.
"""
from __future__ import annotations

import argparse
import urllib.error
import urllib.request
from pathlib import Path

from config import POLICIES_DIR

# A generic client name. Never put the user or the project owner in here.
USER_AGENT = "structured-data-rag/1.0 (corpus fetch)"
TIMEOUT = 120

# filename on disk -> (display title, source URL, what it covers)
REAL_DOCUMENTS: dict[str, tuple[str, str, str]] = {
    "cms_benefit_ch01_inpatient.pdf": (
        "CMS Medicare Benefit Policy Manual, Ch. 1 — Inpatient Hospital Services",
        "https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/bp102c01.pdf",
        "admission types, inpatient coverage, length of stay",
    ),
    "cms_benefit_ch06_outpatient.pdf": (
        "CMS Medicare Benefit Policy Manual, Ch. 6 — Hospital Services Covered Under Part B",
        "https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/bp102c06.pdf",
        "observation status, outpatient services",
    ),
    "cms_benefit_ch15_covered_services.pdf": (
        "CMS Medicare Benefit Policy Manual, Ch. 15 — Covered Medical and Other Health Services",
        "https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/bp102c15.pdf",
        "coverage rules, physician services, drugs and biologicals",
    ),
    "cms_benefit_ch16_exclusions.pdf": (
        "CMS Medicare Benefit Policy Manual, Ch. 16 — General Exclusions From Coverage",
        "https://www.cms.gov/regulations-and-guidance/guidance/manuals/downloads/bp102c16.pdf",
        "what is not covered, and why",
    ),
    "hipaa_45cfr164_privacy_security.pdf": (
        "45 CFR Part 164 — Security and Privacy (HIPAA)",
        "https://www.govinfo.gov/content/pkg/CFR-2024-title45-vol2/pdf/CFR-2024-title45-vol2-part164.pdf",
        "patient rights, medical records, privacy, disclosures",
    ),
    "hipaa_45cfr160_administrative.pdf": (
        "45 CFR Part 160 — General Administrative Requirements (HIPAA)",
        "https://www.govinfo.gov/content/pkg/CFR-2024-title45-vol2/pdf/CFR-2024-title45-vol2-part160.pdf",
        "definitions, compliance, enforcement",
    ),
}

REAL_TITLES = {name: title for name, (title, _, _) in REAL_DOCUMENTS.items()}


def fingerprint() -> str:
    """
    A digest of the corpus as it currently sits on disk.

    Name and size of every PDF, which is enough to notice a document added,
    removed or replaced without reading hundreds of megabytes. The eval
    harness folds this into its index cache key: chunk size and embedding
    model are not sufficient on their own, because the SAME settings over a
    DIFFERENT corpus need a different index.
    """
    import hashlib

    if not POLICIES_DIR.exists():
        return "nocorpus"

    parts = sorted(
        (path.name, path.stat().st_size)
        for path in POLICIES_DIR.glob("*.pdf")
    )
    if not parts:
        return "nocorpus"

    digest = hashlib.sha256()
    for name, size in parts:
        digest.update(f"{name}:{size}\0".encode())
    return digest.hexdigest()[:12]


def present() -> list[str]:
    """Which real documents are actually on disk right now."""
    return [name for name in REAL_DOCUMENTS if (POLICIES_DIR / name).exists()]


def fetch(force: bool = False) -> list[str]:
    """
    Download any missing documents into the policies directory.

    Downloads are data, never code: they are parsed by pypdf and nothing else.
    A failure is reported and skipped rather than raised, so one dead link
    cannot stop the rest of the corpus from arriving.
    """
    POLICIES_DIR.mkdir(parents=True, exist_ok=True)
    fetched = []

    for name, (title, url, _covers) in REAL_DOCUMENTS.items():
        path = POLICIES_DIR / name
        if path.exists() and not force:
            print(f"  have {name} ({path.stat().st_size // 1024} KB)")
            continue

        print(f"  fetching {name} ...")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                payload = response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"    FAILED: {exc}. Skipping {name}.")
            continue

        if not payload.startswith(b"%PDF"):
            print(f"    FAILED: {url} did not return a PDF. Skipping {name}.")
            continue

        # Write via a temp file so an interrupted fetch cannot leave a
        # truncated PDF that pypdf will later choke on.
        tmp = path.with_suffix(".pdf.part")
        tmp.write_bytes(payload)
        tmp.replace(path)
        fetched.append(name)
        print(f"    saved {len(payload) // 1024} KB — {title}")

    missing = [n for n in REAL_DOCUMENTS if not (POLICIES_DIR / n).exists()]
    if missing:
        print(f"\n  {len(missing)} document(s) still missing: {', '.join(missing)}")
        print("  Government URLs move. Check the source site and update corpus.py.")

    return fetched


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch the real policy corpus.")
    parser.add_argument("--force", action="store_true", help="re-download everything")
    args = parser.parse_args()

    print(f"Fetching the real corpus into {POLICIES_DIR}")
    fetch(force=args.force)

    have = present()
    print(f"\n{len(have)}/{len(REAL_DOCUMENTS)} real documents present.")
    if have:
        print("Rebuild the index to pick them up:  make rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
