"""Builds a synthetic "merged" batch out of N repeated runs of the SAME model:
for each group, keeps only the agentic diagnostics whose (node, target,
category) is reported by at least --min-runs of the input runs, merging their
messages and picking the first available fix (in the order the batches were
given on the command line). Output is written in the same
eval_runs/<batch-id>/<group>/ layout Stage 1 produces, so score_eval.py can
score it directly.

Usage:
    python3 merge_runs.py --out-batch-id merged-gpt-6-luna-atleast2of3 --min-runs 2 \
        final-gpt-6-luna-effort-high-run1 final-gpt-6-luna-effort-high-run2 final-gpt-6-luna-effort-high-run3
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
RUNS_DIR = STUDY_DIR / "eval_runs"

SEP = "\n\n" + "-" * 40 + "\n\n"


def load_agentic_diagnostics(group_dir: Path) -> list[dict[str, object]]:
    """Only "missing" diagnostics -- "redundant" ones are filtered out here,
    before merging, since the merge is built for the missing-dependency
    recall/precision study."""
    exit_code_path = group_dir / "exit_code"
    if not exit_code_path.exists() or exit_code_path.read_text().strip() != "0":
        return []
    payload = json.loads((group_dir / "stdout.json").read_text())
    diagnostics = payload.get("diagnostics", [])
    return [
        d for d in diagnostics
        if str(d.get("origin", "")).startswith("agentic-check:") and d.get("category") == "missing"
    ]


def merge_group(batch_labels: list[tuple[str, Path]], min_runs: int) -> list[dict[str, object]]:
    # key -> list of (run_label, diagnostic) in canonical batch order
    by_key: dict[tuple[str, str, str], list[tuple[str, dict[str, object]]]] = {}
    for label, batch_dir in batch_labels:
        seen_keys_this_run: set[tuple[str, str, str]] = set()
        for d in load_agentic_diagnostics(batch_dir):
            key = (str(d["node"]), str(d["target"]), str(d["category"]))
            if key in seen_keys_this_run:
                continue  # one contribution per run per key, even if a run reported it twice
            seen_keys_this_run.add(key)
            by_key.setdefault(key, []).append((label, d))

    merged: list[dict[str, object]] = []
    for (node, target, category), contributions in by_key.items():
        if len(contributions) < min_runs:
            continue
        message = SEP.join(f"[{label}]\n{d['message']}" for label, d in contributions)
        fix = next((d["fix"] for _, d in contributions if d.get("fix") is not None), None)
        merged.append({
            "category": category,
            "severity": contributions[0][1].get("severity", "warning"),
            "message": message,
            "node": node,
            "target": target,
            "fix": fix,
            "origin": f"agentic-check:merged({len(contributions)}/{len(batch_labels)})",
        })
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("batches", nargs="+", help="Source batch-ids (repeated runs of the SAME model), in canonical tie-break order")
    parser.add_argument("--out-batch-id", required=True)
    parser.add_argument("--min-runs", type=int, default=2)
    args = parser.parse_args()

    batch_dirs = [(b, RUNS_DIR / b) for b in args.batches]
    for label, d in batch_dirs:
        if not d.is_dir():
            raise SystemExit(f"no such batch: {d}")

    group_names = sorted(p.name for p in batch_dirs[0][1].iterdir() if p.is_dir())
    out_dir = RUNS_DIR / args.out_batch_id
    out_dir.mkdir(parents=True, exist_ok=True)

    for group_name in group_names:
        per_batch_group_dirs = [(label, d / group_name) for label, d in batch_dirs]
        for label, gd in per_batch_group_dirs:
            if not gd.is_dir():
                raise SystemExit(f"group {group_name!r} missing from batch {label!r}")

        merged_diagnostics = merge_group(per_batch_group_dirs, args.min_runs)

        # meta.json (repo/resolved_sha/module_dir/cases) is identical across all
        # source batches for a given group_name -- take it from the first one.
        source_meta = json.loads((per_batch_group_dirs[0][1] / "meta.json").read_text())
        group_out = out_dir / group_name
        group_out.mkdir(parents=True, exist_ok=True)
        meta = {
            "repo": source_meta["repo"],
            "parent_sha": source_meta["parent_sha"],
            "resolved_sha": source_meta["resolved_sha"],
            "module_dir": source_meta["module_dir"],
            "profile": f"merged(min_runs={args.min_runs}): {','.join(args.batches)}",
            "effort": None,
            "temperature": None,
            "system_prompt": "merged",
            "cases": source_meta["cases"],
        }
        (group_out / "meta.json").write_text(json.dumps(meta, indent=2))
        (group_out / "stdout.json").write_text(json.dumps({"diagnostics": merged_diagnostics}, indent=2))
        (group_out / "stderr.log").write_text("")
        (group_out / "duration_seconds").write_text("0")
        (group_out / "exit_code").write_text("0")

    print(f"wrote merged batch to {out_dir} ({len(group_names)} groups)")


if __name__ == "__main__":
    main()
