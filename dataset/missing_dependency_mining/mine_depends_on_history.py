"""Mine a local git history for real-world "missing dependency" fixes.

Looks for commits that add a `depends_on = [...]` entry to a resource/module
block that already existed before the commit, where the newly-referenced
target also already existed before the commit (i.e. this isn't a `depends_on`
that ships alongside a brand-new resource — it's a fix retrofitted onto two
resources that were already sitting next to each other, unlinked).

Works purely off local git history (no GitHub API / `gh` needed): repos like
GoogleCloudPlatform/cloud-foundation-fabric squash-merge PRs with `(#1234)`
in the commit subject, which is enough to reconstruct the PR URL.

For each candidate, optionally rebuilds dependency_fixer's own dependency
graph from the pre-fix snapshot of the affected module directory and checks
whether the target was already implicitly reachable via attribute references
(DependencyGraph.implicit_edges). If not, the PR's depends_on was encoding a
dependency with no textual trace in the code beforehand — exactly the class
of bug the tool's LLM stage exists to catch, and the interesting subset for a
recall-test dataset. If it *was* already reachable, the depends_on was
redundant belt-and-suspenders, not a missing-dependency bug.

Usage:
    uv run test_dataset/missing_dependency_mining/mine_depends_on_history.py \\
        --repo /path/to/cloud-foundation-fabric \\
        --out report.json \\
        [--limit N] [--no-verify] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

_PR_RE = re.compile(r"\(#(\d+)\)\s*$")
_RESOURCE_HEADER_RE = re.compile(
    r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"\s*\{', re.MULTILINE
)
_MODULE_HEADER_RE = re.compile(r'^\s*module\s+"([^"]+)"\s*\{', re.MULTILINE)
_DATA_HEADER_RE = re.compile(r'^\s*data\s+"([^"]+)"\s+"([^"]+)"\s*\{', re.MULTILINE)
_DEPENDS_ON_RE = re.compile(r"depends_on\s*=\s*\[")


def run_git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def show_blob(repo: Path, rev: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(repo), "show", f"{rev}:{path}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def find_matching_brace(text: str, open_idx: int) -> int:
    """Index of the `}` that closes the `{` at open_idx (naive but robust for HCL)."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


@dataclass
class Block:
    address: str  # e.g. "google_storage_bucket.foo" / "module.foo" / "data.google_project.foo"
    body: str


def extract_blocks(content: str) -> dict[str, Block]:
    blocks: dict[str, Block] = {}
    for regex, fmt in (
        (_RESOURCE_HEADER_RE, lambda m: f"{m.group(1)}.{m.group(2)}"),
        (_MODULE_HEADER_RE, lambda m: f"module.{m.group(1)}"),
        (_DATA_HEADER_RE, lambda m: f"data.{m.group(1)}.{m.group(2)}"),
    ):
        for m in regex.finditer(content):
            open_idx = content.index("{", m.end() - 1)
            close_idx = find_matching_brace(content, open_idx)
            if close_idx == -1:
                continue
            address = fmt(m)
            blocks[address] = Block(address=address, body=content[open_idx : close_idx + 1])
    return blocks


def parse_depends_on_targets(body: str) -> set[str]:
    m = _DEPENDS_ON_RE.search(body)
    if not m:
        return set()
    open_idx = body.index("[", m.end() - 1)
    depth = 0
    close_idx = -1
    for i in range(open_idx, len(body)):
        if body[i] == "[":
            depth += 1
        elif body[i] == "]":
            depth -= 1
            if depth == 0:
                close_idx = i
                break
    if close_idx == -1:
        return set()
    raw = body[open_idx + 1 : close_idx]
    targets: set[str] = set()
    for entry in raw.split(","):
        entry = entry.strip()
        entry = entry.split("#", 1)[0].strip()  # trailing line comment
        if not entry:
            continue
        # strip subscripts like `["key"]` / `[count.index]` / `[each.key]`
        base = entry.split("[", 1)[0].strip()
        if base:
            targets.add(base)
    return targets


@dataclass
class Candidate:
    pr_number: int | None
    pr_url: str | None
    commit_url: str
    commit_sha: str
    parent_sha: str
    commit_subject: str
    commit_date: str
    file: str
    module_dir: str
    holder_address: str
    added_targets: list[str] = field(default_factory=list)
    pre_existing_targets: list[str] = field(default_factory=list)
    already_implicit: dict[str, bool] | None = None  # target -> was reachable pre-fix
    verify_error: str | None = None


def list_changed_tf_files(repo: Path, sha: str) -> list[tuple[str, str]]:
    """Returns (status, path) for modified (not added/deleted) .tf files in a commit."""
    out = run_git(
        repo, "diff-tree", "--no-commit-id", "--name-status", "-r", sha, "--", "*.tf"
    )
    result = []
    for line in out.splitlines():
        if not line.strip():
            continue
        status, path = line.split("\t", 1)
        if status == "M":
            result.append((status, path))
    return result


def dir_has_address(repo: Path, rev: str, dirpath: str, address: str) -> bool:
    """Whether `address` (e.g. 'module.foo') is declared by any .tf file directly
    inside dirpath at the given revision (non-recursive, matching HCL module scoping)."""
    out = run_git(repo, "ls-tree", "--name-only", rev, "--", f"{dirpath}/", check=False)
    for name in out.splitlines():
        if not name.endswith(".tf"):
            continue
        content = show_blob(repo, rev, name)
        if content is None:
            continue
        if address in extract_blocks(content):
            return True
    return False


def mine(repo: Path, limit: int | None, verbose: bool, github_repo_slug: str) -> list[Candidate]:
    # Deliberately NOT `git log -G'depends_on'`: -G only matches commits whose
    # *added/removed* diff lines contain the pattern. A commit that appends a
    # new entry to an already-existing multi-line `depends_on = [...]` list
    # never touches the `depends_on = [` line itself (it stays as unchanged
    # context), so -G silently drops it — this is exactly what happened with
    # cloud-foundation-fabric PR #3496 (appended `google_org_policy_policy.default`
    # to an existing depends_on list; caught here, missed by -G). Scanning
    # every commit that touches a .tf file is slower but doesn't have that
    # false-negative.
    # --no-merges: merge commits already contribute nothing here today, since
    # list_changed_tf_files()'s plain `git diff-tree` (no -m/-c) prints an
    # empty diff for any merge commit by default — but that's incidental
    # behavior of a flag we don't pass, not a documented guarantee, so exclude
    # them explicitly rather than rely on it silently continuing to hold.
    shas = [
        s
        for s in run_git(
            repo, "log", "--no-merges", "--format=%H", "--", "*.tf"
        ).splitlines()
        if s.strip()
    ]
    if limit:
        shas = shas[:limit]

    candidates: list[Candidate] = []
    for idx, sha in enumerate(shas):
        if verbose:
            print(f"[{idx + 1}/{len(shas)}] {sha[:10]}", file=sys.stderr)

        subject = run_git(repo, "log", "-1", "--format=%s", sha).strip()
        date = run_git(repo, "log", "-1", "--format=%cI", sha).strip()
        pr_match = _PR_RE.search(subject)
        pr_number = int(pr_match.group(1)) if pr_match else None
        pr_url = f"https://github.com/{github_repo_slug}/pull/{pr_number}" if pr_number else None
        parent_sha = f"{sha}^"

        try:
            changed = list_changed_tf_files(repo, sha)
        except RuntimeError:
            continue  # e.g. root commit with no parent

        for _status, path in changed:
            old_content = show_blob(repo, parent_sha, path)
            new_content = show_blob(repo, sha, path)
            if old_content is None or new_content is None:
                continue

            old_blocks = extract_blocks(old_content)
            new_blocks = extract_blocks(new_content)
            dirpath = str(Path(path).parent)

            for address, new_block in new_blocks.items():
                old_block = old_blocks.get(address)
                if old_block is None:
                    continue  # block itself is new in this commit — not our case

                old_targets = parse_depends_on_targets(old_block.body)
                new_targets = parse_depends_on_targets(new_block.body)
                added = new_targets - old_targets
                if not added:
                    continue

                confirmed_added = []
                for target in sorted(added):
                    if target.startswith(("var.", "local.", "each.", "count.")):
                        continue
                    if dir_has_address(repo, parent_sha, dirpath, target):
                        confirmed_added.append(target)

                if confirmed_added:
                    candidates.append(
                        Candidate(
                            pr_number=pr_number,
                            pr_url=pr_url,
                            commit_url=f"https://github.com/{github_repo_slug}/commit/{sha}",
                            commit_sha=sha,
                            parent_sha=parent_sha,
                            commit_subject=subject,
                            commit_date=date,
                            file=path,
                            module_dir=dirpath,
                            holder_address=address,
                            added_targets=confirmed_added,
                            pre_existing_targets=sorted(old_targets),
                        )
                    )
    return candidates


def enrich_pr_numbers(candidates: list[Candidate], github_repo_slug: str, verbose: bool) -> None:
    """Best-effort: for candidates whose commit subject had no `(#NNNN)`, ask
    GitHub's commit->PR association API (unauthenticated, no `gh` needed)."""
    shas_needed = sorted({c.commit_sha for c in candidates if c.pr_number is None})
    resolved: dict[str, tuple[int, str]] = {}
    for sha in shas_needed:
        url = f"https://api.github.com/repos/{github_repo_slug}/commits/{sha}/pulls"
        req = urllib.request.Request(
            url, headers={"Accept": "application/vnd.github+json", "User-Agent": "dependency-fixer-miner"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                pulls = json.loads(resp.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            if verbose:
                print(f"  PR lookup failed for {sha[:10]}: {e}", file=sys.stderr)
            continue
        merged = [p for p in pulls if p.get("merged_at")] or pulls
        if merged:
            resolved[sha] = (merged[0]["number"], merged[0]["html_url"])

    for c in candidates:
        if c.commit_sha in resolved:
            c.pr_number, c.pr_url = resolved[c.commit_sha]


def verify_candidates(repo: Path, candidates: list[Candidate], verbose: bool) -> None:
    """For each candidate, rebuild the tool's own DependencyGraph from the
    pre-fix snapshot of the whole repo and check implicit reachability."""
    from dependency_fixer.graph import DependencyGraph
    from dependency_fixer.parser import TerraformProject

    by_parent_sha: dict[str, list[Candidate]] = {}
    for c in candidates:
        by_parent_sha.setdefault(c.parent_sha, []).append(c)

    for i, (parent_sha, group) in enumerate(by_parent_sha.items()):
        if verbose:
            print(
                f"verifying commit-group [{i + 1}/{len(by_parent_sha)}] {parent_sha[:12]}"
                f" ({len(group)} candidate(s))",
                file=sys.stderr,
            )
        with tempfile.TemporaryDirectory(prefix="cff-archive-") as tmp:
            tmp_path = Path(tmp)
            archive = subprocess.run(
                ["git", "-C", str(repo), "archive", parent_sha],
                capture_output=True,
            )
            if archive.returncode != 0:
                for c in group:
                    c.verify_error = archive.stderr.decode(errors="replace")
                continue
            with tempfile.TemporaryFile() as tarf:
                tarf.write(archive.stdout)
                tarf.seek(0)
                with tarfile.open(fileobj=tarf) as tf:
                    tf.extractall(str(tmp_path), filter="data")

            for c in group:
                module_path = tmp_path / c.module_dir
                if not module_path.is_dir():
                    c.verify_error = f"module dir not present in archive: {c.module_dir}"
                    continue
                try:
                    project = TerraformProject(str(module_path))
                    graph = DependencyGraph(project)
                except Exception as e:  # noqa: BLE001 — best-effort, record and move on
                    c.verify_error = f"{type(e).__name__}: {e}"
                    continue

                holder_node = _to_node(c.holder_address)
                reachable = _implicit_reachable(graph, holder_node)
                results: dict[str, bool] = {}
                for target in c.added_targets:
                    results[target] = _to_node(target) in reachable
                c.already_implicit = results


def _to_node(address: str) -> str:
    """Root-scope node id for a bare address like 'module.foo' / 'data.t.n' / 'type.name'."""
    if address.startswith(("module.", "data.")):
        return f":{address}"
    return f":resource.{address}"


def _implicit_reachable(graph, start: str) -> set[str]:
    seen: set[str] = set()
    stack = list(graph.implicit_edges.get(start, ()))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.implicit_edges.get(current, ()))
    return seen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="Path to the local git clone to mine.")
    parser.add_argument("--out", required=True, help="Path to write the JSON report to.")
    parser.add_argument("--limit", type=int, default=None, help="Only scan the first N candidate commits.")
    parser.add_argument("--no-verify", action="store_true", help="Skip the graph-reachability verification pass.")
    parser.add_argument(
        "--no-enrich-pr",
        action="store_true",
        help="Skip GitHub commit->PR lookup for commits with no `(#NNNN)` in their subject.",
    )
    parser.add_argument(
        "--github-repo",
        default="GoogleCloudPlatform/cloud-foundation-fabric",
        help="owner/repo slug used for PR URLs and the enrichment API.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    candidates = mine(repo, args.limit, args.verbose, args.github_repo)
    print(f"Found {len(candidates)} candidate (holder, added target) fixes.", file=sys.stderr)

    if not args.no_enrich_pr:
        enrich_pr_numbers(candidates, args.github_repo, args.verbose)

    if not args.no_verify:
        verify_candidates(repo, candidates, args.verbose)

    def rec(c: Candidate) -> dict:
        d = c.__dict__.copy()
        return d

    Path(args.out).write_text(json.dumps([rec(c) for c in candidates], indent=2))

    true_positives = [
        c
        for c in candidates
        if c.already_implicit is not None
        and any(not v for v in c.already_implicit.values())
    ]
    print(
        f"Wrote {len(candidates)} candidates to {args.out} "
        f"({len(true_positives)} with at least one target NOT already implicitly "
        "reachable pre-fix — the interesting subset).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
