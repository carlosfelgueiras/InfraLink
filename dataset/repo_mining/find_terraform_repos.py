"""Find candidate Terraform repositories via the GitHub GraphQL API.

Searches GitHub for repositories carrying a given topic and written
primarily in a given language, ordered by star count descending (via the
`sort:stars-desc` search qualifier), then scans down that list applying
activity filters until `--top-k` matches are collected:
  - the default branch's last commit is at most `--max-age-days` old
  - the default branch has at least `--min-commits` commits total
  - the repo's license (as GitHub classifies it) is in `--permissive-licenses`
Forks and archived repos are excluded via GitHub search qualifiers unless
`--include-forks` / `--include-archived` is passed. "Default branch" here
means whatever GitHub reports as each repo's own default branch (main,
master, or otherwise) — not literally the branch named "main".

License handling: repos with no detected license at all are always
excluded (no LICENSE file means no rights granted, not "unknown"). Repos
that have a LICENSE file GitHub couldn't classify against a known SPDX
license (its `licenseInfo.spdxId` comes back as "NOASSERTION") are still
included by default, with a warning printed to stderr and a `# WARNING`
suffix on their output line, since these need a human to actually open the
file — pass `--exclude-unrecognized-license` to drop them instead.

A single GraphQL query per page of results returns star count, the default
branch's last-commit date and exact commit count, and license info
together, so no per-repo follow-up requests are needed.

Output is just `url`, one per line (plus a `# WARNING` suffix on lines with
an unrecognized license), in star-descending order — meant as a
manual-review candidate list, not a full report.

Requires a GitHub token with public repo read access, via --token or the
GITHUB_TOKEN env var (loaded from a .env file if python-dotenv is installed).

Usage:
    uv run test_dataset/repo_mining/find_terraform_repos.py \\
        --top-k 50 \\
        [--topic terraform] [--language HCL] \\
        [--max-age-days 365] [--min-commits 100] \\
        [--permissive-licenses MIT,Apache-2.0,...] [--exclude-unrecognized-license] \\
        [--include-forks] [--include-archived] \\
        [--out repos.txt]
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

try:
    import certifi

    # macOS python.org builds don't use the system trust store, so urllib's
    # default SSL context often can't find any root CAs (CERTIFICATE_VERIFY_FAILED:
    # unable to get local issuer certificate) unless pointed at certifi's bundle.
    _SSL_CONTEXT: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _SSL_CONTEXT = None

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
PAGE_SIZE = 100  # GitHub search API's max page size
SEARCH_RESULT_CAP = 1000  # GitHub search API's hard cap on total results

# GitHub's SPDX license classifier uses "NOASSERTION" for a LICENSE file it
# found but couldn't match to a known license.
UNRECOGNIZED_LICENSE_SPDX_ID = "NOASSERTION"

DEFAULT_PERMISSIVE_LICENSES = (
    "MIT",
    "MIT-0",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "0BSD",
    "ISC",
    "Unlicense",
    "Zlib",
    "BSL-1.0",
)

_SEARCH_QUERY = """
query($searchQuery: String!, $first: Int!, $after: String) {
  rateLimit {
    remaining
    resetAt
  }
  search(query: $searchQuery, type: REPOSITORY, first: $first, after: $after) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      ... on Repository {
        nameWithOwner
        url
        stargazerCount
        licenseInfo {
          spdxId
          name
        }
        defaultBranchRef {
          target {
            ... on Commit {
              committedDate
              history {
                totalCount
              }
            }
          }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class Filters:
    topic: str
    language: str
    max_age_days: int
    min_commits: int
    include_forks: bool
    include_archived: bool
    permissive_licenses: frozenset[str]
    exclude_unrecognized_license: bool
    top_k: int


@dataclass(frozen=True)
class RepoResult:
    name_with_owner: str
    url: str
    stars: int
    last_commit_days_ago: int
    commit_count: int
    license_spdx_id: str | None
    license_unrecognized: bool


def build_search_query(filters: Filters) -> str:
    parts = [f"topic:{filters.topic}", f"language:{filters.language}", "sort:stars-desc"]
    if not filters.include_archived:
        parts.append("archived:false")
    if filters.include_forks:
        parts.append("fork:true")
    return " ".join(parts)


def graphql_request(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        GITHUB_GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "dependency-fixer-repo-mining",
        },
        method="POST",
    )
    backoff = 5.0
    last_error: urllib.error.HTTPError | None = None
    for _ in range(6):
        try:
            with urllib.request.urlopen(request, timeout=30, context=_SSL_CONTEXT) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if "errors" in payload:
                    raise RuntimeError(f"GraphQL error: {payload['errors']}")
                result: dict[str, Any] = payload["data"]
                return result
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code in (403, 502, 503, 504):
                retry_after = error.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else backoff
                print(
                    f"  ({error.code} from GitHub, waiting {wait:.0f}s before retrying)",
                    file=sys.stderr,
                )
                time.sleep(wait)
                backoff *= 2
                continue
            raise
    assert last_error is not None
    raise last_error


def scan(filters: Filters, token: str) -> list[RepoResult]:
    search_query = build_search_query(filters)
    print(f"search query: {search_query}", file=sys.stderr)

    cutoff = datetime.now(timezone.utc) - timedelta(days=filters.max_age_days)
    results: list[RepoResult] = []
    cursor: str | None = None
    scanned = 0

    while len(results) < filters.top_k and scanned < SEARCH_RESULT_CAP:
        data = graphql_request(
            token,
            _SEARCH_QUERY,
            {"searchQuery": search_query, "first": PAGE_SIZE, "after": cursor},
        )

        rate_limit = data["rateLimit"]
        if rate_limit["remaining"] < 50:
            reset_at = datetime.fromisoformat(rate_limit["resetAt"].replace("Z", "+00:00"))
            wait = max(0.0, (reset_at - datetime.now(timezone.utc)).total_seconds()) + 1
            print(f"  (rate limit low, sleeping {wait:.0f}s until reset)", file=sys.stderr)
            time.sleep(wait)

        search = data["search"]
        nodes = search["nodes"]
        if not nodes:
            break

        for node in nodes:
            scanned += 1
            branch = node.get("defaultBranchRef")
            if branch is None or branch.get("target") is None:
                continue  # empty repo, no commits on the default branch

            commit = branch["target"]
            committed_at = datetime.fromisoformat(commit["committedDate"].replace("Z", "+00:00"))
            commit_count = commit["history"]["totalCount"]

            if committed_at < cutoff or commit_count < filters.min_commits:
                continue

            license_info = node.get("licenseInfo")
            if license_info is None:
                continue  # no LICENSE file detected at all
            spdx_id = license_info.get("spdxId")
            license_unrecognized = not spdx_id or spdx_id == UNRECOGNIZED_LICENSE_SPDX_ID
            if license_unrecognized:
                if filters.exclude_unrecognized_license:
                    continue
            elif spdx_id not in filters.permissive_licenses:
                continue

            age_days = (datetime.now(timezone.utc) - committed_at).days
            results.append(
                RepoResult(
                    name_with_owner=node["nameWithOwner"],
                    url=node["url"],
                    stars=node["stargazerCount"],
                    last_commit_days_ago=age_days,
                    commit_count=commit_count,
                    license_spdx_id=spdx_id,
                    license_unrecognized=license_unrecognized,
                )
            )
            warning = " [WARNING: unrecognized license, verify manually]" if license_unrecognized else ""
            print(
                f"  [{len(results)}/{filters.top_k}] match: {node['nameWithOwner']} "
                f"(stars={node['stargazerCount']}, commits={commit_count}, "
                f"last_commit={age_days}d ago, license={spdx_id or 'unrecognized'}){warning}",
                file=sys.stderr,
            )
            if len(results) >= filters.top_k:
                break

        print(f"  scanned {scanned} candidates so far...", file=sys.stderr)

        page_info = search["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        cursor = page_info["endCursor"]

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--topic", default="terraform")
    parser.add_argument("--language", default="HCL")
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=730,
        help="max days since the default branch's last commit (default: 730)",
    )
    parser.add_argument(
        "--min-commits",
        type=int,
        default=200,
        help="min total commits on the default branch (default: 200)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=50,
        help="number of matching repos to collect (default: 100)",
    )
    parser.add_argument(
        "--include-forks",
        action="store_true",
        help="don't exclude forks (excluded by default)",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="don't exclude archived repos (excluded by default)",
    )
    parser.add_argument(
        "--permissive-licenses",
        default=",".join(DEFAULT_PERMISSIVE_LICENSES),
        help=(
            "comma-separated SPDX license ids to allow, as GitHub classifies them "
            f"(default: {','.join(DEFAULT_PERMISSIVE_LICENSES)}). Repos with no "
            "detected license are always excluded."
        ),
    )
    parser.add_argument(
        "--exclude-unrecognized-license",
        action="store_true",
        help=(
            "drop repos whose LICENSE file GitHub couldn't classify, instead of "
            "including them with a manual-review warning (the default)"
        ),
    )
    parser.add_argument(
        "--token", default=None, help="GitHub token (defaults to GITHUB_TOKEN env var)"
    )
    parser.add_argument(
        "--out", type=Path, default=None, help="write results here instead of stdout"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("error: no GitHub token (pass --token or set GITHUB_TOKEN)", file=sys.stderr)
        raise SystemExit(1)

    filters = Filters(
        topic=args.topic,
        language=args.language,
        max_age_days=args.max_age_days,
        min_commits=args.min_commits,
        include_forks=args.include_forks,
        include_archived=args.include_archived,
        permissive_licenses=frozenset(
            license_id.strip() for license_id in args.permissive_licenses.split(",") if license_id.strip()
        ),
        exclude_unrecognized_license=args.exclude_unrecognized_license,
        top_k=args.top_k,
    )

    results = scan(filters, token)

    lines = [
        f"{r.url}\t# WARNING: unrecognized license ({r.license_spdx_id or 'none'}), verify manually"
        if r.license_unrecognized
        else r.url
        for r in results
    ]
    output = "\n".join(lines) + ("\n" if lines else "")
    if args.out:
        args.out.write_text(output)
        print(f"wrote {len(results)} repos to {args.out}", file=sys.stderr)
    else:
        sys.stdout.write(output)

    unrecognized_count = sum(1 for r in results if r.license_unrecognized)
    print(f"done: {len(results)}/{filters.top_k} requested matches found", file=sys.stderr)
    if unrecognized_count:
        print(
            f"  ({unrecognized_count} of those have an unrecognized license — see "
            "'# WARNING' lines in the output)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
