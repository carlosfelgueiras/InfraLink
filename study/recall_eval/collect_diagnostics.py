"""Flattens one run batch's per-group diagnostics into a single JSON file, one
record per diagnostic, each carrying the context (repo, commit, module
entrypoint) a human reviewer needs to actually go look at the code. Meant as
input to a later sampling step for a manual precision evaluation — this
script does no sampling or scoring itself, only collection.

By default only agentic-check diagnostics are included (origin starting with
"agentic-check:") -- RedundantDependsOnCheck's mechanical diagnostics are
deterministic/rule-based and aren't the thing a precision study is about;
pass --include-mechanical to keep them too.

Pass --category missing to keep only "missing"-category diagnostics -- a
no-op on a merge_runs.py batch (already missing-only by construction) but
needed on a raw single-model batch, which also carries "redundant" findings.

Usage:
    python3 collect_diagnostics.py --batch-id final-deepseek-v4.1-flash-1017-effort-high-run2 \
        --category missing --out diagnostics_deepseek_run2.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
RUNS_DIR = STUDY_DIR / "eval_runs"


def load_group_diagnostics(group_dir: Path) -> list[dict[str, object]]:
    exit_code_path = group_dir / "exit_code"
    if not exit_code_path.exists() or exit_code_path.read_text().strip() != "0":
        return []
    payload = json.loads((group_dir / "stdout.json").read_text())
    diagnostics = payload.get("diagnostics", [])
    return diagnostics if isinstance(diagnostics, list) else []


def collect(batch_dir: Path, *, include_mechanical: bool, category: str | None) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    next_id = 1
    for group_dir in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
        meta = json.loads((group_dir / "meta.json").read_text())
        for d in load_group_diagnostics(group_dir):
            origin = str(d.get("origin", ""))
            if not include_mechanical and not origin.startswith("agentic-check:"):
                continue
            if category is not None and d.get("category") != category:
                continue
            records.append({
                "id": next_id,
                "repo": meta["repo"],
                "resolved_sha": meta["resolved_sha"],
                "module_dir": meta["module_dir"],
                "category": d.get("category"),
                "severity": d.get("severity"),
                "node": d.get("node"),
                "target": d.get("target"),
                "message": d.get("message"),
                "fix": d.get("fix"),
                "origin": origin,
                "group_dir": group_dir.name,
            })
            next_id += 1
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--include-mechanical", action="store_true")
    parser.add_argument("--category", choices=["missing", "redundant"], default=None)
    args = parser.parse_args()

    batch_dir = RUNS_DIR / args.batch_id
    if not batch_dir.is_dir():
        raise SystemExit(f"no such batch: {batch_dir}")

    records = collect(batch_dir, include_mechanical=args.include_mechanical, category=args.category)
    args.out.write_text(json.dumps(records, indent=2))
    print(f"wrote {len(records)} diagnostics to {args.out}")


if __name__ == "__main__":
    main()
