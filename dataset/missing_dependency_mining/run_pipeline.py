"""Orchestrate clone -> mine -> filter -> merge across every repo in repos/.

Layout this expects (all siblings of this script):
    repos/<repo-dir-name>/       one manually-cloned git checkout per repo
    results/<repo-dir-name>_candidates.json    mine_depends_on_history.py output
    results/<repo-dir-name>_trustworthy.json   filter_trustworthy.py output
    results/logs/<repo-dir-name>.log           combined stderr of both stages
    results/all_candidates.json                merge of every *_candidates.json
    results/all_trustworthy.json               merge of every *_trustworthy.json
    repos.json                                  optional override: {"dir-name": "owner/repo"}

For each repo directory:
- The GitHub `owner/repo` slug is auto-detected from `git remote get-url origin`
  (handles both SSH and HTTPS remote URLs), unless repos.json overrides it.
- Mining is skipped if `<repo>_candidates.json` already exists, unless --force
  (mining is the slow, git+GitHub-API-bound stage). Filtering always re-runs —
  it's cheap, pure-local JSON filtering, so filter-criteria changes take effect
  dataset-wide just by re-running this script, with no re-mining needed.
- Both sub-scripts are always invoked with --verbose; their combined stderr is
  captured in full to results/logs/<repo>.log regardless of this script's own
  --verbose flag, so nothing is lost even in the default (quiet) run.
- This script's own --verbose only controls what it prints to ITS OWN stderr:
  a short per-repo status line as each repo finishes, plus a fuller final
  report. Without --verbose, only a single final summary line is printed.

Usage:
    python3 run_pipeline.py [--force] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
REPOS_DIR = BASE_DIR / "repos"
RESULTS_DIR = BASE_DIR / "results"
LOGS_DIR = RESULTS_DIR / "logs"
OVERRIDE_FILE = BASE_DIR / "repos.json"
MINE_SCRIPT = BASE_DIR / "mine_depends_on_history.py"
FILTER_SCRIPT = BASE_DIR / "filter_trustworthy.py"

_SSH_REMOTE_RE = re.compile(r"^git@[^:]+:(?P<slug>.+?)(\.git)?/?$")
_HTTPS_REMOTE_RE = re.compile(r"^https?://[^/]+/(?P<slug>.+?)(\.git)?/?$")


def detect_github_slug(repo_path: Path, overrides: dict[str, str]) -> str | None:
    if repo_path.name in overrides:
        return overrides[repo_path.name]
    result = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    url = result.stdout.strip()
    for regex in (_SSH_REMOTE_RE, _HTTPS_REMOTE_RE):
        m = regex.match(url)
        if m:
            return m.group("slug")
    return None


def run_stage(cmd: list[str], log_lines: list[str], header: str) -> tuple[bool, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    log_lines.append(f"=== {header} ===")
    log_lines.append(f"$ {' '.join(cmd)}")
    log_lines.append(result.stderr)
    if result.returncode != 0:
        log_lines.append(f"[exit code {result.returncode}]")
    return result.returncode == 0, result.stderr


def process_repo(
    repo_path: Path, overrides: dict[str, str], force: bool, verbose: bool, idx: int, total: int
) -> dict | None:
    name = repo_path.name
    candidates_path = RESULTS_DIR / f"{name}_candidates.json"
    trustworthy_path = RESULTS_DIR / f"{name}_trustworthy.json"
    log_path = LOGS_DIR / f"{name}.log"
    log_lines: list[str] = []

    slug = detect_github_slug(repo_path, overrides)
    if slug is None:
        print(
            f"[{idx}/{total}] {name}: could not detect a GitHub owner/repo slug "
            f"(no parseable 'origin' remote) — add it to {OVERRIDE_FILE.name} to include this repo. Skipping.",
            file=sys.stderr,
        )
        return None

    if verbose:
        print(f"[{idx}/{total}] {name} ({slug}): starting...", file=sys.stderr)

    if candidates_path.exists() and not force:
        log_lines.append(f"=== mine_depends_on_history.py ===\nskipped: {candidates_path.name} already exists (use --force to re-mine)")
        mined_ok = True
    else:
        mined_ok, _ = run_stage(
            [
                sys.executable, str(MINE_SCRIPT),
                "--repo", str(repo_path),
                "--out", str(candidates_path),
                "--github-repo", slug,
                "--verbose",
            ],
            log_lines, "mine_depends_on_history.py",
        )

    if not mined_ok or not candidates_path.exists():
        log_path.write_text("\n".join(log_lines) + "\n")
        print(f"[{idx}/{total}] {name}: mining FAILED — see {log_path}", file=sys.stderr)
        return None

    filtered_ok, _ = run_stage(
        [
            sys.executable, str(FILTER_SCRIPT),
            "--in", str(candidates_path),
            "--out", str(trustworthy_path),
            "--verbose",
        ],
        log_lines, "filter_trustworthy.py",
    )
    log_path.write_text("\n".join(log_lines) + "\n")

    if not filtered_ok or not trustworthy_path.exists():
        print(f"[{idx}/{total}] {name}: filtering FAILED — see {log_path}", file=sys.stderr)
        return None

    n_candidates = len(json.loads(candidates_path.read_text()))
    n_trustworthy = len(json.loads(trustworthy_path.read_text()))

    if verbose:
        print(
            f"[{idx}/{total}] {name} ({slug}): {n_candidates} candidates, "
            f"{n_trustworthy} trustworthy — log: {log_path.relative_to(BASE_DIR)}",
            file=sys.stderr,
        )

    return {"repo": name, "slug": slug, "candidates": n_candidates, "trustworthy": n_trustworthy}


def merge_results() -> tuple[int, int]:
    # Exclude our own merged output — it also matches "*_candidates.json" /
    # "*_trustworthy.json" (as "all_candidates.json" etc), so without this a
    # second run would fold the merge back into itself and double every count.
    merged_names = {"all_candidates.json", "all_trustworthy.json"}

    all_candidates = []
    all_trustworthy = []
    for path in sorted(RESULTS_DIR.glob("*_candidates.json")):
        if path.name in merged_names:
            continue
        repo = path.name[: -len("_candidates.json")]
        for record in json.loads(path.read_text()):
            all_candidates.append({"repo": repo, **record})
    for path in sorted(RESULTS_DIR.glob("*_trustworthy.json")):
        if path.name in merged_names:
            continue
        repo = path.name[: -len("_trustworthy.json")]
        for record in json.loads(path.read_text()):
            all_trustworthy.append({"repo": repo, **record})

    (RESULTS_DIR / "all_candidates.json").write_text(json.dumps(all_candidates, indent=2))
    (RESULTS_DIR / "all_trustworthy.json").write_text(json.dumps(all_trustworthy, indent=2))
    return len(all_candidates), len(all_trustworthy)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="Re-mine repos even if a *_candidates.json already exists.")
    parser.add_argument("--verbose", action="store_true", help="Print a per-repo status line plus a fuller final report.")
    args = parser.parse_args()

    RESULTS_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

    overrides: dict[str, str] = {}
    if OVERRIDE_FILE.exists():
        overrides = json.loads(OVERRIDE_FILE.read_text())

    repo_dirs = sorted(p for p in REPOS_DIR.iterdir() if p.is_dir())
    reports = []
    for idx, repo_path in enumerate(repo_dirs, start=1):
        report = process_repo(repo_path, overrides, args.force, args.verbose, idx, len(repo_dirs))
        if report:
            reports.append(report)

    n_all_candidates, n_all_trustworthy = merge_results()

    if args.verbose:
        print(file=sys.stderr)
        print("-- per-repo summary --", file=sys.stderr)
        for r in reports:
            print(f"  {r['repo']}: {r['candidates']} candidates, {r['trustworthy']} trustworthy", file=sys.stderr)
        print(file=sys.stderr)

    print(
        f"Processed {len(reports)}/{len(repo_dirs)} repos. "
        f"Merged: {n_all_candidates} candidates, {n_all_trustworthy} trustworthy "
        f"-> {RESULTS_DIR / 'all_candidates.json'}, {RESULTS_DIR / 'all_trustworthy.json'}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
