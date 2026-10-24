"""Side-by-side report over several eval_runs/ batches: recall (via
score_eval.py's own grading), how many diagnostics each batch emitted, run
failures, wall time, and token usage -- plus a per-pair outcome matrix and
per-model run-to-run stability.

Token/request counts come from dependency-fixer's "run complete" log line in
each group's stderr.log. Synthetic batches (merge_runs.py output) have no
logs of their own; their cost is the sum of their source batches, resolved
recursively through meta.json's "merged(...): a,b,c" profile.

Usage:
    python3 report_runs.py --out-dir reports/2026-10-23 \
        default \
        final-gpt-6-luna-effort-high-run1 final-gpt-6-luna-effort-high-run2 ... \
        --stability gpt-6-luna=final-gpt-6-luna-effort-high-run1,final-gpt-6-luna-effort-high-run2,...
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from pathlib import Path

from score_eval import RUNS_DIR, load_group_diagnostics, score_group

_RUN_COMPLETE = re.compile(
    r"run complete — requests=(\d+) tool_calls=(\d+) input_tokens=(\d+) output_tokens=(\d+)"
)
_EFFORT_SENT = re.compile(r"'reasoning_effort': '(\w+)'")
_MERGED_PROFILE = re.compile(r"^merged\(min_runs=(\d+)\): (.+)$")


def group_dirs(batch: str) -> list[Path]:
    return sorted(p for p in (RUNS_DIR / batch).iterdir() if p.is_dir())


def source_batches(batch: str) -> tuple[int, list[str]] | None:
    meta = json.loads((group_dirs(batch)[0] / "meta.json").read_text())
    match = _MERGED_PROFILE.match(str(meta.get("profile", "")))
    if match is None:
        return None
    return int(match.group(1)), match.group(2).split(",")


def leaf_batches(batch: str) -> list[str]:
    sources = source_batches(batch)
    if sources is None:
        return [batch]
    return [leaf for source in sources[1] for leaf in leaf_batches(source)]


def usage_of_real_batch(batch: str) -> dict[str, object]:
    requests = tool_calls = input_tokens = output_tokens = 0
    durations: list[float] = []
    efforts: Counter[str] = Counter()
    groups_without_usage = 0
    for group_dir in group_dirs(batch):
        stderr = (group_dir / "stderr.log").read_text(errors="replace")
        match = _RUN_COMPLETE.search(stderr)
        if match is None:
            groups_without_usage += 1
        else:
            requests += int(match.group(1))
            tool_calls += int(match.group(2))
            input_tokens += int(match.group(3))
            output_tokens += int(match.group(4))
        effort = _EFFORT_SENT.search(stderr)
        efforts[effort.group(1) if effort else "(none sent)"] += 1
        duration_path = group_dir / "duration_seconds"
        if duration_path.exists():
            durations.append(float(duration_path.read_text()))
    return {
        "requests": requests,
        "tool_calls": tool_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "groups_without_usage": groups_without_usage,
        "effort_sent": ",".join(f"{k}x{v}" for k, v in efforts.most_common()),
        "wall_time_total_s": round(sum(durations), 1),
        "wall_time_median_s": round(statistics.median(durations), 1) if durations else None,
        "wall_time_max_s": round(max(durations), 1) if durations else None,
    }


def summarize_batch(batch: str) -> tuple[dict[str, object], dict[tuple[str, str, str], str]]:
    meta = json.loads((group_dirs(batch)[0] / "meta.json").read_text())
    results = []
    missing_emitted = 0
    failed_groups: Counter[str] = Counter()
    for group_dir in group_dirs(batch):
        group_results, _ = score_group(group_dir)
        results.extend(group_results)
        diagnostics, status = load_group_diagnostics(group_dir)
        if diagnostics is None:
            exit_code_path = group_dir / "exit_code"
            failed_groups[exit_code_path.read_text().strip() if exit_code_path.exists() else "incomplete"] += 1
        else:
            missing_emitted += sum(
                1 for d in diagnostics
                if d.get("category") == "missing" and str(d.get("origin", "")).startswith("agentic-check:")
            )

    counts = Counter(r.outcome for r in results)
    total = len(results)
    scored = total - counts["error"]
    sources = source_batches(batch)

    row: dict[str, object] = {
        "batch": batch,
        "profile": meta.get("profile") if sources is None else f"synthetic: min_runs={sources[0]} of {len(sources[1])}",
        "effort_flag": meta.get("effort"),
        "groups": len(group_dirs(batch)),
        "failed_groups": sum(failed_groups.values()),
        "failed_groups_detail": ",".join(f"{k}x{v}" for k, v in failed_groups.items()),
        "pairs": total,
        "hit": counts["hit"],
        "reversed": counts["reversed"],
        "miss": counts["miss"],
        "error": counts["error"],
        "recall_excl_errors": round(counts["hit"] / scored, 4) if scored else None,
        "recall_errors_as_miss": round(counts["hit"] / total, 4) if total else None,
        "missing_diagnostics_emitted": missing_emitted,
    }

    leaves = leaf_batches(batch)
    usage = [usage_of_real_batch(leaf) for leaf in leaves]
    row["underlying_runs"] = len(leaves)
    for key in ("requests", "tool_calls", "input_tokens", "output_tokens", "groups_without_usage", "wall_time_total_s"):
        row[key] = round(sum(u[key] for u in usage), 1) if key == "wall_time_total_s" else sum(u[key] for u in usage)
    row["effort_sent"] = usage[0]["effort_sent"] if len(leaves) == 1 else "; ".join(sorted({str(u["effort_sent"]) for u in usage}))
    row["wall_time_median_s"] = usage[0]["wall_time_median_s"] if len(leaves) == 1 else None
    row["wall_time_max_s"] = usage[0]["wall_time_max_s"] if len(leaves) == 1 else None

    outcomes = {(r.group_dir, r.holder_address, r.target): r.outcome for r in results}
    return row, outcomes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("batches", nargs="+")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--stability", action="append", default=[],
        help="name=batch1,batch2,... -- repeated runs of one model; reports how many runs hit each pair",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    matrix: dict[tuple[str, str, str], dict[str, str]] = {}
    for batch in args.batches:
        row, outcomes = summarize_batch(batch)
        rows.append(row)
        for key, outcome in outcomes.items():
            matrix.setdefault(key, {})[batch] = outcome

    summary_path = args.out_dir / "summary.csv"
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    matrix_path = args.out_dir / "pair_matrix.csv"
    with matrix_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["group_dir", "holder_address", "target", *args.batches])
        for (group, holder, target), per_batch in sorted(matrix.items()):
            writer.writerow([group, holder, target, *(per_batch.get(b, "") for b in args.batches)])

    stability_rows = []
    for spec in args.stability:
        name, batches = spec.split("=", 1)
        batch_list = batches.split(",")
        hits_per_pair = Counter(
            sum(1 for b in batch_list if per_batch_outcomes.get(b) == "hit")
            for per_batch_outcomes in matrix.values()
        )
        stability_rows.append({"model": name, "runs": len(batch_list), **{
            f"hit_in_{k}_runs": hits_per_pair[k] for k in range(len(batch_list) + 1)
        }})
    if stability_rows:
        stability_path = args.out_dir / "stability.csv"
        with stability_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(stability_rows[0]))
            writer.writeheader()
            writer.writerows(stability_rows)

    print(json.dumps({"summary": rows, "stability": stability_rows}, indent=2))


if __name__ == "__main__":
    main()
