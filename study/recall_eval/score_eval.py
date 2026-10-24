"""Stage 2 of the missing-dependency recall study: scores Stage 1's output
(study/recall_eval/eval_runs/<batch-id>/*/) against the dataset annotations
each group's meta.json already carries, and reports recall.

Self-contained by design: doesn't re-load or re-group all_trustworthy.json —
each group's meta.json already embeds exactly the dataset rows that group was
run against (Stage 1 wrote them there for this reason), so Stage 2 only ever
reads eval_runs/.

Grading unit is one (holder_address, target) pair — the finest-grained ground
truth unit (one dataset row can list multiple added_targets). A pair is:
  - "hit"      if some diagnostic has category == "missing" and
               (node, target) == (f":resource.{holder}", f":resource.{target}"
               exactly.
  - "reversed" if no hit, but some "missing" diagnostic has node/target
               swapped relative to the pair — informative for manual
               inspection (the model found *something* about these two
               resources, but asserted the dependency backwards), not counted
               as a hit.
  - "miss"     otherwise.
  - "error"    if the group's run itself failed (non-zero/"TIMEOUT" exit code
               or unparseable stdout.json) — excluded from the recall
               denominator by default (see --count-errors-as-miss), reported
               separately so a run failure is never silently read as "the
               model didn't find it."

This is a single run per case (see run_eval.py's README) — report the
resulting recall as a noisy point estimate, not a precise measurement.

Usage:
    python3 score_eval.py --batch-id default
    python3 score_eval.py --batch-id default --csv scores.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

STUDY_DIR = Path(__file__).resolve().parent
RUNS_DIR = STUDY_DIR / "eval_runs"

Outcome = Literal["hit", "reversed", "miss", "error"]


@dataclass(frozen=True)
class PairResult:
    group_dir: str
    repo: str
    resolved_sha: str
    module_dir: str
    holder_address: str
    target: str
    outcome: Outcome
    pr_url: str


# Matches graph.py's _node_id(): a resource's local key gets "resource." inserted
# (bare dataset addresses are always "<type>.<name>"), but module/data/var/output/
# provider addresses already come in their own local-key shape and just need the
# root ":" prefix — NOT a "resource." insertion (seen in the data: holder/target
# addresses aren't always resources, e.g. "module.base" -> "module.eks-addons").
_NON_RESOURCE_PREFIXES = ("module.", "data.", "var.", "output.", "provider.")


def node_id(address: str) -> str:
    if address.startswith(_NON_RESOURCE_PREFIXES):
        return f":{address}"
    return f":resource.{address}"


def load_group_diagnostics(group_dir: Path) -> tuple[list[dict[str, object]] | None, str]:
    """Returns (diagnostics, status). status is "ok" if the run succeeded and
    stdout.json parsed; otherwise a short reason, and diagnostics is None."""
    exit_code_path = group_dir / "exit_code"
    if not exit_code_path.exists():
        return None, "no exit_code (run incomplete?)"
    exit_code = exit_code_path.read_text().strip()
    if exit_code != "0":
        return None, f"non-zero exit_code={exit_code!r}"

    try:
        payload = json.loads((group_dir / "stdout.json").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"stdout.json unreadable/invalid: {exc}"

    diagnostics = payload.get("diagnostics")
    if not isinstance(diagnostics, list):
        return None, "stdout.json missing a 'diagnostics' list"
    return diagnostics, "ok"


def count_agent_diagnostics(diagnostics: list[dict[str, object]] | None) -> int:
    """How many diagnostics (any category) the agentic check itself emitted —
    i.e. excluding RedundantDependsOnCheck's mechanical ones, which share the
    same stdout.json but are tagged with a different origin."""
    if diagnostics is None:
        return 0
    return sum(1 for d in diagnostics if str(d.get("origin", "")).startswith("agentic-check:"))


def score_group(group_dir: Path) -> tuple[list[PairResult], int]:
    meta = json.loads((group_dir / "meta.json").read_text())
    repo = meta["repo"]
    resolved_sha = meta["resolved_sha"]
    module_dir = meta["module_dir"]
    cases = meta["cases"]

    diagnostics, status = load_group_diagnostics(group_dir)
    missing_diagnostics = (
        [d for d in diagnostics if d.get("category") == "missing"] if diagnostics is not None else []
    )
    agent_diagnostic_count = count_agent_diagnostics(diagnostics)

    results: list[PairResult] = []
    for case in cases:
        holder = case["holder_address"]
        for target in case["added_targets"]:
            if diagnostics is None:
                outcome: Outcome = "error"
            else:
                holder_id, target_id = node_id(holder), node_id(target)
                if any(d.get("node") == holder_id and d.get("target") == target_id for d in missing_diagnostics):
                    outcome = "hit"
                elif any(d.get("node") == target_id and d.get("target") == holder_id for d in missing_diagnostics):
                    outcome = "reversed"
                else:
                    outcome = "miss"
            results.append(PairResult(
                group_dir=group_dir.name,
                repo=repo,
                resolved_sha=resolved_sha,
                module_dir=module_dir,
                holder_address=holder,
                target=target,
                outcome=outcome,
                pr_url=case.get("pr_url", ""),
            ))
    return results, agent_diagnostic_count


def score_batch(batch_dir: Path) -> tuple[list[PairResult], int]:
    results: list[PairResult] = []
    total_agent_diagnostics = 0
    for group_dir in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
        group_results, agent_diagnostic_count = score_group(group_dir)
        results.extend(group_results)
        total_agent_diagnostics += agent_diagnostic_count
    return results, total_agent_diagnostics


def print_report(results: list[PairResult], *, total_agent_diagnostics: int, count_errors_as_miss: bool) -> None:
    counts = Counter(r.outcome for r in results)
    total = len(results)
    errors = counts["error"]
    denominator = total if count_errors_as_miss else total - errors
    hits = counts["hit"]
    recall = hits / denominator if denominator else float("nan")

    print(f"total pairs: {total}")
    print(f"  hit:      {counts['hit']}")
    print(f"  reversed: {counts['reversed']}  (found the two resources, asserted the wrong direction)")
    print(f"  miss:     {counts['miss']}")
    print(f"  error:    {counts['error']}  (run itself failed — excluded from recall unless --count-errors-as-miss)")
    print(f"recall: {hits}/{denominator} = {recall:.1%}")
    print(f"total diagnostics emitted by the agent (any category, all groups): {total_agent_diagnostics}")
    print()

    print("by repo:")
    by_repo: dict[str, Counter[str]] = {}
    for r in results:
        by_repo.setdefault(r.repo, Counter())[r.outcome] += 1
    for repo, c in sorted(by_repo.items()):
        repo_total = sum(c.values())
        repo_denom = repo_total if count_errors_as_miss else repo_total - c["error"]
        repo_recall = c["hit"] / repo_denom if repo_denom else float("nan")
        print(f"  {repo}: {c['hit']}/{repo_denom} = {repo_recall:.1%} (n={repo_total})")
    print()

    print("by target resource type (top 15 by pair count):")
    by_target_type: dict[str, Counter[str]] = {}
    for r in results:
        target_type = r.target.split(".", 1)[0]
        by_target_type.setdefault(target_type, Counter())[r.outcome] += 1
    ranked = sorted(by_target_type.items(), key=lambda kv: -sum(kv[1].values()))[:15]
    for target_type, c in ranked:
        t_total = sum(c.values())
        t_denom = t_total if count_errors_as_miss else t_total - c["error"]
        t_recall = c["hit"] / t_denom if t_denom else float("nan")
        print(f"  {target_type}: {c['hit']}/{t_denom} = {t_recall:.1%} (n={t_total})")


def write_csv(results: list[PairResult], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["group_dir", "repo", "resolved_sha", "module_dir", "holder_address", "target", "outcome", "pr_url"])
        for r in results:
            writer.writerow([r.group_dir, r.repo, r.resolved_sha, r.module_dir, r.holder_address, r.target, r.outcome, r.pr_url])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--batch-id", default="default")
    parser.add_argument("--csv", type=Path, default=None, help="Write the full per-pair matrix here")
    parser.add_argument(
        "--count-errors-as-miss", action="store_true",
        help="Include run-failure pairs in the recall denominator as misses, instead of excluding them",
    )
    args = parser.parse_args()

    batch_dir = RUNS_DIR / args.batch_id
    if not batch_dir.is_dir():
        print(f"no such batch: {batch_dir}", file=sys.stderr)
        raise SystemExit(1)

    results, total_agent_diagnostics = score_batch(batch_dir)
    if not results:
        print(f"no groups found under {batch_dir}", file=sys.stderr)
        raise SystemExit(1)

    print_report(results, total_agent_diagnostics=total_agent_diagnostics, count_errors_as_miss=args.count_errors_as_miss)

    if args.csv is not None:
        write_csv(results, args.csv)
        print(f"\nwrote {len(results)} rows to {args.csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
