"""Stage 1 of the missing-dependency recall study: run dependency-fixer's
agentic check against every (repo, parent_sha, module_dir) group implied by
dataset/missing_dependency_mining/results/all_trustworthy.json, and persist
everything (stdout, stderr/logs, exit code, timing) for later scoring.

This does NOT do the scoring (Stage 2) — it only produces the raw run outputs
Stage 2 will later be graded against.

One run per group (no repeats): this is an early/idea-paper pass, kept cheap
on purpose. A single run per case is a noisy point estimate of recall, not a
precise one — worth saying so wherever these numbers get reported.

Checkout strategy: repos are NOT re-cloned. dataset/missing_dependency_mining/
repos/<owner>__<repo> already holds full (non-shallow) clones made by the
mining pipeline itself — every repo referenced by all_trustworthy.json is
already there (verified: 15/15). This script only adds a `git worktree` per
distinct (repo, parent_sha) on top of that existing clone, so the full repo
tree is on disk (not just module_dir) and any relative module `source = ...`
reference the module under test makes — even one reaching outside module_dir —
resolves correctly.

Usage:
    python3 run_eval.py --profile bedrock-claude-sonnet --dry-run
    python3 run_eval.py --profile bedrock-claude-sonnet --limit 5
    python3 run_eval.py --profile bedrock-claude-sonnet --repo Azure__terraform-azurerm-caf-enterprise-scale
    python3 run_eval.py --profile bedrock-claude-sonnet            # full batch
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
DEPENDENCY_FIXER_ROOT = STUDY_DIR.parent.parent
DEFAULT_DATASET = DEPENDENCY_FIXER_ROOT / "dataset/missing_dependency_mining/results/all_trustworthy.json"
REPOS_CACHE_DIR = DEPENDENCY_FIXER_ROOT / "dataset/missing_dependency_mining/repos"
WORKTREES_DIR = STUDY_DIR / "worktrees"
RUNS_DIR = STUDY_DIR / "eval_runs"


@dataclass(frozen=True)
class GroupKey:
    repo: str
    parent_sha: str
    module_dir: str


def load_groups(dataset_path: Path) -> dict[GroupKey, list[dict[str, object]]]:
    """Groups dataset rows by (repo, parent_sha, module_dir) — the unit of one
    dependency-fixer invocation. Multiple rows (even multiple added_targets
    within one row) can share a group."""
    rows = json.loads(dataset_path.read_text())
    groups: dict[GroupKey, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        key = GroupKey(repo=row["repo"], parent_sha=row["parent_sha"], module_dir=row["module_dir"])
        groups[key].append(row)
    return groups


def resolve_sha(repo_path: Path, revision: str) -> str:
    """Resolves a git revision expression (e.g. "<sha>^") to a concrete SHA,
    so worktree paths are stable and reusable across groups that happen to
    name the same parent commit two different ways."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", revision],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def ensure_worktree(repo: str, resolved_sha: str) -> Path:
    """Creates (or reuses) a `git worktree` for (repo, resolved_sha) on top of
    the mining pipeline's existing full clone in REPOS_CACHE_DIR. Never
    re-clones — that clone already has the full history we need."""
    repo_path = REPOS_CACHE_DIR / repo
    if not repo_path.is_dir():
        raise FileNotFoundError(
            f"{repo_path} not found — expected the mining pipeline's existing clone there"
        )

    worktree_path = WORKTREES_DIR / repo / resolved_sha[:12]
    if worktree_path.is_dir():
        return worktree_path

    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "--detach", str(worktree_path), resolved_sha],
        capture_output=True, text=True, check=True,
    )
    return worktree_path


def slugify_module_dir(module_dir: str) -> str:
    if module_dir in (".", ""):
        return "root"
    return module_dir.replace("/", "__")


def group_output_dir(batch_id: str, key: GroupKey, resolved_sha: str) -> Path:
    name = f"{key.repo}__{resolved_sha[:12]}__{slugify_module_dir(key.module_dir)}"
    return RUNS_DIR / batch_id / name


def already_done(output_dir: Path) -> bool:
    return (output_dir / "exit_code").exists()


def run_dependency_fixer(
    target_path: Path,
    *,
    profile: str,
    effort: str | None,
    temperature: float | None,
    system_prompt: str | None,
    timeout_seconds: int,
) -> tuple[str, str, int | str, float]:
    """Runs dependency-fixer against target_path. Returns (stdout, stderr,
    exit_code, duration_seconds). exit_code is the string "TIMEOUT" if the
    run was killed for taking too long, rather than raising — one hung case
    must not stall the whole batch."""
    command = [
        "uv", "run", "python", "-m", "dependency_fixer.main",
        str(target_path),
        "--agentic-profile", profile,
        "--json",
        "--log-level", "DEBUG",
    ]
    if effort is not None:
        command += ["--agentic-effort", effort]
    if temperature is not None:
        command += ["--agentic-temperature", str(temperature)]
    if system_prompt is not None:
        command += ["--agentic-system-prompt", system_prompt]

    start = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=DEPENDENCY_FIXER_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        duration = time.monotonic() - start
        return result.stdout, result.stderr, result.returncode, duration
    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return stdout, stderr, "TIMEOUT", duration


def write_group_output(
    output_dir: Path,
    *,
    key: GroupKey,
    resolved_sha: str,
    rows: list[dict[str, object]],
    profile: str,
    effort: str | None,
    temperature: float | None,
    system_prompt: str | None,
    stdout: str,
    stderr: str,
    exit_code: int | str,
    duration_seconds: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "repo": key.repo,
        "parent_sha": key.parent_sha,
        "resolved_sha": resolved_sha,
        "module_dir": key.module_dir,
        "profile": profile,
        "effort": effort,
        "temperature": temperature,
        "system_prompt": system_prompt or "default",
        "cases": rows,
    }
    (output_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    (output_dir / "stdout.json").write_text(stdout)
    (output_dir / "stderr.log").write_text(stderr)
    (output_dir / "duration_seconds").write_text(str(duration_seconds))
    # exit_code written last — its presence marks this group as done (see already_done)
    (output_dir / "exit_code").write_text(str(exit_code))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", required=True, help="--agentic-profile value to pass through to dependency-fixer")
    parser.add_argument("--effort", choices=["minimal", "low", "medium", "high"], default=None)
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument(
        "--system-prompt", default=None,
        help="--agentic-system-prompt value to pass through (default: dependency-fixer's own default)",
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--batch-id", default="default", help="Subdirectory under eval_runs/ to write into")
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N groups (cheap pilot runs)")
    parser.add_argument("--repo", default=None, help="Only process groups from this one repo (debugging)")
    parser.add_argument("--force", action="store_true", help="Re-run groups even if already marked done")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the planned groups/commands without checking anything out or invoking dependency-fixer",
    )
    args = parser.parse_args()

    groups = load_groups(args.dataset)
    keys = sorted(groups, key=lambda k: (k.repo, k.parent_sha, k.module_dir))
    if args.repo is not None:
        keys = [k for k in keys if k.repo == args.repo]
    if args.limit is not None:
        keys = keys[: args.limit]

    print(f"{len(keys)} groups to process ({sum(len(groups[k]) for k in keys)} dataset rows)", file=sys.stderr)

    for key in keys:
        rows = groups[key]

        if args.dry_run:
            print(f"[dry-run] {key.repo} @ {key.parent_sha} :: {key.module_dir} ({len(rows)} rows)")
            continue

        repo_path = REPOS_CACHE_DIR / key.repo
        resolved_sha = resolve_sha(repo_path, key.parent_sha)
        output_dir = group_output_dir(args.batch_id, key, resolved_sha)

        if already_done(output_dir) and not args.force:
            print(f"skip (already done): {output_dir}", file=sys.stderr)
            continue

        worktree_path = ensure_worktree(key.repo, resolved_sha)
        target_path = worktree_path / key.module_dir

        print(f"running: {key.repo} @ {resolved_sha[:12]} :: {key.module_dir}", file=sys.stderr)
        stdout, stderr, exit_code, duration = run_dependency_fixer(
            target_path,
            profile=args.profile,
            effort=args.effort,
            temperature=args.temperature,
            system_prompt=args.system_prompt,
            timeout_seconds=args.timeout_seconds,
        )
        write_group_output(
            output_dir,
            key=key,
            resolved_sha=resolved_sha,
            rows=rows,
            profile=args.profile,
            effort=args.effort,
            temperature=args.temperature,
            system_prompt=args.system_prompt,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_seconds=duration,
        )
        print(f"  -> exit_code={exit_code} duration={duration:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
