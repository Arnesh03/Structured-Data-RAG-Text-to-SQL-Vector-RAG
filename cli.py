"""
Command-line interface - the same pipeline without a browser.

Usage:
  python cli.py                                # interactive REPL
  python cli.py "average billing by insurer?"  # one-shot question
  python cli.py --setup [--force]              # build database + vector store only
  python cli.py --demo                         # run a scripted set of both routes
  python cli.py --stats                        # print the dashboard aggregates
"""
import argparse
import sys

from pipeline import EXAMPLE_QUESTIONS, ROUTE_ICONS, answer, initialize

DEMO_QUESTIONS = [
    "How many admissions are there for each medical condition?",
    "What is the average billing amount by insurance provider?",
    "Which medical condition has the longest average length of stay?",
    "What do the emergency department triage levels mean?",
    "Who qualifies for financial assistance or charity care?",
    "What is the inpatient blood glucose target for diabetic patients?",
]


def render(result: dict) -> str:
    """Render a pipeline result as plain text for a terminal."""
    if not result.get("ok"):
        return f"\n[error] {result['answer']}\n"

    route = result["route"]
    lines = [
        "",
        f"{ROUTE_ICONS.get(route, '?')}  route: {route}   ({result['elapsed']:.1f}s)",
        "",
        result["answer"].strip(),
        "",
    ]
    if route == "sql":
        lines += [f"  SQL ({result.get('row_count', 0)} rows): "
                  + result.get("sql_query", "N/A"), ""]
    else:
        titles = [s["title"] for s in result.get("sources") or []]
        lines += ["  Sources: " + (", ".join(titles) or "N/A"), ""]
    return "\n".join(lines)


def ask(question: str) -> bool:
    """Ask one question and print the result. Returns True on success."""
    print(f"\n> {question}")
    result = answer(question)
    print(render(result))
    return bool(result.get("ok"))


def print_stats() -> None:
    """Print the dashboard aggregates as a quick sanity check on the data."""
    import analytics

    data = analytics.dashboard()
    kpis = data["kpis"]
    print("\nDataset overview")
    print(f"  admissions      {kpis['total_admissions']:,}")
    print(f"  unique patients {kpis['unique_patients']:,}")
    print(f"  date range      {kpis['first_admission']} to {kpis['last_admission']}")
    print(f"  total billing   ${kpis['total_billing']:,.2f}")
    print(f"  avg stay        {kpis['avg_stay_days']} days")
    print("\nAdmissions by condition")
    for row in data["by_condition"]:
        print(f"  {row['name']:<14} {row['admissions']:>6,}  "
              f"avg ${row['avg_billing']:>10,.2f}  {row['avg_stay']:>4} days")


def repl() -> None:
    """Interactive question loop."""
    print("Type a question, or 'exit' to quit. '?' lists examples.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if question.lower() in {"exit", "quit", "q"}:
            return
        if question == "?":
            for ex in EXAMPLE_QUESTIONS:
                print(f"  [{ex['route']}] {ex['q']}")
            continue
        if question:
            print(render(answer(question)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Healthcare Structured Data RAG CLI")
    parser.add_argument("question", nargs="*", help="question to ask")
    parser.add_argument("--setup", action="store_true", help="build data only, then exit")
    parser.add_argument("--force", action="store_true", help="rebuild data from scratch")
    parser.add_argument("--demo", action="store_true", help="run scripted demo questions")
    parser.add_argument("--stats", action="store_true", help="print dataset aggregates")
    args = parser.parse_args()

    initialize(warm=not (args.setup or args.stats), force=args.force)

    if args.setup:
        return 0

    if args.stats:
        print_stats()
        return 0

    if args.demo:
        failures = sum(0 if ask(q) else 1 for q in DEMO_QUESTIONS)
        print(f"\n{len(DEMO_QUESTIONS) - failures}/{len(DEMO_QUESTIONS)} questions answered.")
        return 1 if failures else 0

    if args.question:
        return 0 if ask(" ".join(args.question)) else 1

    repl()
    return 0


if __name__ == "__main__":
    sys.exit(main())
