"""Looks up one diagnostic by id in a collect_diagnostics.py / sample_diagnostics.py
/ simplify_diagnostics.py output file and prints it readably -- real newlines
instead of a JSON blob's "\\n" escapes, which make the (often long) message
field hard to read.

Works with either schema: the full one (repo/resolved_sha/module_dir/category/
severity/node/target/message/fix/origin/group_dir) or the simplified one
(id/node/target/message/github_url) -- only the fields present are printed.

Usage:
    python3 show_diagnostic.py sample_30_merged_deepseek_atleast2of3.json 164
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_RULE = "=" * 80


def find_by_id(records: list[dict[str, object]], target_id: int) -> dict[str, object]:
    for record in records:
        if record.get("id") == target_id:
            return record
    available = sorted(r["id"] for r in records if "id" in r)
    raise SystemExit(f"no diagnostic with id {target_id} found (available ids: {available})")


def render(record: dict[str, object]) -> str:
    lines: list[str] = [_RULE, f"id: {record['id']}", _RULE]

    if "category" in record or "severity" in record:
        lines.append(f"{record.get('category', '?')} ({record.get('severity', '?')})")

    if "node" in record and "target" in record:
        lines.append(f"{record['node']}\n  -> depends on ->\n{record['target']}")

    if "repo" in record:
        lines.append(f"\nrepo:        {record['repo']}")
        lines.append(f"commit:      {record.get('resolved_sha', '?')}")
        lines.append(f"module_dir:  {record.get('module_dir', '?')}")
    if "github_url" in record:
        lines.append(f"\ngithub: {record['github_url']}")

    if "group_dir" in record:
        lines.append(f"group_dir:   {record['group_dir']}")
    if "origin" in record:
        lines.append(f"origin:      {record['origin']}")

    lines.append(f"\n{_RULE}\nmessage:\n{_RULE}\n{record.get('message', '')}")

    fix = record.get("fix")
    if fix:
        lines.append(f"\n{_RULE}\nfix: set `{fix['field']}` to:\n{fix['expression']}")

    lines.append(_RULE)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=Path)
    parser.add_argument("id", type=int)
    args = parser.parse_args()

    records = json.loads(args.file.read_text())
    record = find_by_id(records, args.id)
    print(render(record))


if __name__ == "__main__":
    main()
