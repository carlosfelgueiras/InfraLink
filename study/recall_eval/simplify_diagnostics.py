"""Simplifies a collect_diagnostics.py / sample_diagnostics.py output file
down to what an expert reviewer actually needs: the diagnostic's id and
message, plus a single GitHub URL (built from repo + commit + module
entrypoint) pointing straight at the code in question.

Usage:
    python3 simplify_diagnostics.py --in sample_30_merged_deepseek_atleast2of3.json \
        --out sample_30_merged_deepseek_atleast2of3.simplified.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def github_url(repo: str, resolved_sha: str, module_dir: str) -> str:
    owner, name = repo.split("__", 1)
    base = f"https://github.com/{owner}/{name}/tree/{resolved_sha}"
    if module_dir in (".", ""):
        return base
    return f"{base}/{module_dir}"


def simplify(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "id": r["id"],
            "node": r["node"],  # the resource that has (or should have) the dependency
            "target": r["target"],  # the resource it depends on (or is missing a dependency on)
            "message": r["message"],
            "github_url": github_url(str(r["repo"]), str(r["resolved_sha"]), str(r["module_dir"])),
        }
        for r in records
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="in_path", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    records = json.loads(args.in_path.read_text())
    simplified = simplify(records)
    args.out.write_text(json.dumps(simplified, indent=2))
    print(f"wrote {len(simplified)} simplified diagnostics to {args.out}")


if __name__ == "__main__":
    main()
