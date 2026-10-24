"""Draws a random sample of N records from a collect_diagnostics.py output
file, writing them out in the same format (so the sample file is a drop-in
subset, ready to hand to expert reviewers).

Usage:
    python3 sample_diagnostics.py --in diagnostics_merged_deepseek_atleast2of3.json \
        --n 30 --seed 42 --out sample_30_merged_deepseek_atleast2of3.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="in_path", type=Path, required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    records = json.loads(args.in_path.read_text())
    if args.n > len(records):
        raise SystemExit(f"--n {args.n} exceeds population size {len(records)}")

    rng = random.Random(args.seed)
    sample = rng.sample(records, args.n)

    args.out.write_text(json.dumps(sample, indent=2))
    print(f"wrote {len(sample)} sampled diagnostics (seed={args.seed}) to {args.out}")


if __name__ == "__main__":
    main()
