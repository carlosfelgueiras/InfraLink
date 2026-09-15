"""Clone a list of GitHub repos into repos/, for run_pipeline.py to later mine.

Input is a plain text file, one GitHub repo base page URL per line, e.g.:
    https://github.com/GoogleCloudPlatform/cloud-foundation-fabric
    https://github.com/terraform-aws-modules/terraform-aws-eks/
Blank lines and lines starting with # are ignored.

Clones are full (no --depth) since mine_depends_on_history.py needs complete
history to scan commits. Each repo lands at repos/<owner>__<repo>/ — the full
slug, not just the repo name, since two different repos can share a bare name
(this came up mining ~40 real repos) and run_pipeline.py's output naming,
logging, and merge tagging all key off the directory name. "__" is the
separator because repo/owner names routinely contain single "-"/"_" already,
which would make a single-character separator ambiguous to split back apart.

If a target directory already exists, it's left untouched and skipped by
default (safe to re-run this script as you extend the list) — pass --update
to `git pull --ff-only` existing ones instead of skipping them.

Usage:
    python3 clone_repos.py repos.txt [--repos-dir repos] [--update]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_REPOS_DIR = BASE_DIR / "repos"

_GITHUB_URL_RE = re.compile(r"^https?://github\.com/(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(\.git)?/?$")


def parse_repo_urls(text_file: Path) -> list[tuple[str, str]]:
    """Returns (clone_url, dir_name) pairs, in file order, skipping blanks/comments.
    dir_name is the full "<owner>__<repo>" slug — see module docstring for why."""
    entries = []
    for lineno, raw in enumerate(text_file.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = _GITHUB_URL_RE.match(line)
        if not m:
            print(f"line {lineno}: not a recognizable GitHub repo URL, skipping: {line!r}", file=sys.stderr)
            continue
        owner, repo = m.group("owner"), m.group("repo")
        entries.append((f"https://github.com/{owner}/{repo}.git", f"{owner}__{repo}"))
    return entries


def clone_or_update(clone_url: str, dir_name: str, repos_dir: Path, update: bool) -> str:
    target = repos_dir / dir_name
    if target.exists():
        if not update:
            print(f"{dir_name}: already exists, skipping (pass --update to pull)", file=sys.stderr)
            return "skipped"
        result = subprocess.run(
            ["git", "-C", str(target), "pull", "--ff-only"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"{dir_name}: update FAILED — {result.stderr.strip()}", file=sys.stderr)
            return "failed"
        print(f"{dir_name}: updated", file=sys.stderr)
        return "updated"

    result = subprocess.run(
        ["git", "clone", clone_url, str(target)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"{dir_name}: clone FAILED — {result.stderr.strip()}", file=sys.stderr)
        return "failed"
    print(f"{dir_name}: cloned", file=sys.stderr)
    return "cloned"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("urls_file", help="Text file with one GitHub repo base URL per line.")
    parser.add_argument("--repos-dir", default=str(DEFAULT_REPOS_DIR), help="Where to clone into (default: repos/ next to this script).")
    parser.add_argument("--update", action="store_true", help="For repos already cloned, `git pull --ff-only` instead of skipping.")
    args = parser.parse_args()

    repos_dir = Path(args.repos_dir).resolve()
    repos_dir.mkdir(parents=True, exist_ok=True)

    entries = parse_repo_urls(Path(args.urls_file))
    counts = {"cloned": 0, "updated": 0, "skipped": 0, "failed": 0}
    for clone_url, dir_name in entries:
        outcome = clone_or_update(clone_url, dir_name, repos_dir, args.update)
        counts[outcome] += 1

    print(
        f"Done: {counts['cloned']} cloned, {counts['updated']} updated, "
        f"{counts['skipped']} skipped, {counts['failed']} failed "
        f"({len(entries)} total URLs) -> {repos_dir}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
