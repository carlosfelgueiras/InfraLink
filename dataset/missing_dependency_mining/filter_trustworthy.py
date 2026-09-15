"""Filter mine_depends_on_history.py's output down to the trustworthy subset.

A candidate is kept only if all of the following hold:
- It has a resolved PR number (pr_number is not null) - so it's traceable
  back to an actual reviewed/merged GitHub PR, not just a bare commit.
- The verification pass succeeded (verify_error is null) - the pre-fix
  module snapshot parsed and its DependencyGraph was built without error.
- At least one added target was NOT already implicitly reachable pre-fix
  (already_implicit has at least one False value) - i.e. it's a genuine
  missing dependency, not just a redundant belt-and-suspenders depends_on.

Usage:
    python3 filter_trustworthy.py --in cff_candidates.json --out cff_trustworthy.json [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys

FILTER_NAMES = ["no_pr_number", "verify_error", "redundant"]


def failed_filters(c: dict) -> list[str]:
    """Returns the names of every filter `c` fails (empty list = trustworthy)."""
    failures = []
    if c.get("pr_number") is None:
        failures.append("no_pr_number")
    if c.get("verify_error") is not None:
        failures.append("verify_error")
    already_implicit = c.get("already_implicit")
    if not already_implicit or not any(not v for v in already_implicit.values()):
        failures.append("redundant")
    return failures


def is_trustworthy(c: dict) -> bool:
    return not failed_filters(c)


def _label(c: dict) -> str:
    pr = f"PR#{c['pr_number']}" if c.get("pr_number") is not None else c.get("commit_sha", "?")[:10]
    return f"{pr} {c.get('file', '?')} {c.get('holder_address', '?')}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="in_path", required=True)
    parser.add_argument("--out", dest="out_path", required=True)
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print a pass/fail line per candidate, plus per-filter failure counts.",
    )
    args = parser.parse_args()

    candidates = json.load(open(args.in_path))

    filter_fail_counts = {name: 0 for name in FILTER_NAMES}
    kept = []
    for c in candidates:
        failures = failed_filters(c)
        if failures:
            for name in failures:
                filter_fail_counts[name] += 1
            if args.verbose:
                print(f"FAIL [{', '.join(failures)}]  {_label(c)}", file=sys.stderr)
        else:
            kept.append(c)
            if args.verbose:
                print(f"PASS  {_label(c)}", file=sys.stderr)

    json.dump(kept, open(args.out_path, "w"), indent=2)

    if args.verbose:
        print(file=sys.stderr)
        print("-- per-filter failure counts --", file=sys.stderr)
        for name in FILTER_NAMES:
            print(f"  {name}: {filter_fail_counts[name]}", file=sys.stderr)
        print(f"  passed all filters: {len(kept)}", file=sys.stderr)
        print(f"  total candidates: {len(candidates)}", file=sys.stderr)

    print(f"{len(kept)}/{len(candidates)} candidates kept -> {args.out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
