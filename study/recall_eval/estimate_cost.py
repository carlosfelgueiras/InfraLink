"""Estimates OpenRouter credit cost for a run batch from the token-usage
numbers pydantic-ai logs in each group's stderr.log (DEBUG-level, as run_eval.py
always sets), multiplied by each model's published per-token pricing.

Idempotent token extraction: stderr.log is huge (DEBUG-level tool-call/token
logs) and carries absolute filesystem paths (bad for a double-blind
replication package). The first time a group is read, its 4 usage numbers are
extracted and cached to usage_tokens.json right next to it -- tiny, and PII-free.
Every later read (including from a copy of this repo that never had the raw
logs at all) uses that file instead and never touches stderr.log again. This
means stderr.log can be deleted/excluded from a release once every group here
has been scored at least once.

This is an ESTIMATE, not the actual billed amount, for three reasons:
  - The logged "usage" blobs always have "cost": null -- OpenRouter only
    populates actual billed cost when a request opts into the `usage.include`
    accounting extension, which this tool's requests don't set. We fall back
    to list pricing x token counts.
  - DeepSeek's pricing has UTC-day/time-of-day tiers (off-peak is ~2x cheaper
    than peak); we use the off-peak tier for all DeepSeek tokens since most
    runs happened late at night, which likely UNDERESTIMATES total DeepSeek
    cost somewhat.
  - "flex" service-tier requests are billed at a discount relative to standard
    pricing (that's the point of flex), but OpenRouter's /models pricing
    endpoint only exposes the standard-tier rate -- gpt-6.1-sol-flex runs are
    therefore an UPPER BOUND, not the real flex price paid.

Token accounting, read off pydantic-ai's logged usage object:
  - input_tokens is the TOTAL prompt size, and cache_write_tokens/
    cache_read_tokens are a BREAKDOWN of it, not additional to it --
    empirically, cache_write_tokens + cache_read_tokens is within ~0.01% of
    input_tokens across millions of logged tokens. So:
      - cache_write_tokens: billed at "input_cache_write" if the model has
                             that price, else at the plain "prompt" rate
      - cache_read_tokens:  billed at "input_cache_read"
      - the remainder (input_tokens - cache_write_tokens - cache_read_tokens,
        i.e. the genuinely uncached sliver): billed at the plain "prompt" rate
  - output_tokens:       billed at "completion" (already includes reasoning
                          tokens -- output_tokens >= reasoning_tokens in every
                          sampled usage blob, so there is no separate add-on)

Usage:
    python3 estimate_cost.py final-gpt-6.1-sol-flex-effort-high-run1 \
        --model openai/gpt-6.1-sol
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

STUDY_DIR = Path(__file__).resolve().parent
RUNS_DIR = STUDY_DIR / "eval_runs"
USAGE_TOKENS_FILENAME = "usage_tokens.json"

_USAGE_RE = re.compile(
    r'"usage":\{"input_tokens":(\d+),"cache_write_tokens":(\d+),'
    r'"cache_read_tokens":(\d+),"output_tokens":(\d+)'
)


def _usage_from_log(log_path: Path) -> tuple[int, int, int, int]:
    input_tokens = cache_write_tokens = cache_read_tokens = output_tokens = 0
    for m in _USAGE_RE.finditer(log_path.read_text(errors="replace")):
        input_tokens += int(m.group(1))
        cache_write_tokens += int(m.group(2))
        cache_read_tokens += int(m.group(3))
        output_tokens += int(m.group(4))
    return input_tokens, cache_write_tokens, cache_read_tokens, output_tokens


def group_usage(group_dir: Path) -> tuple[int, int, int, int] | None:
    """Reads (input, cache_write, cache_read, output) token totals for one
    group, preferring the cached usage_tokens.json if present. If absent but
    stderr.log is, extracts and caches it there for next time. Returns None if
    neither is available (a stripped-down release with logs already removed
    and no cache file -- nothing can be computed for this group)."""
    tokens_path = group_dir / USAGE_TOKENS_FILENAME
    if tokens_path.is_file():
        data = json.loads(tokens_path.read_text())
        return data["input_tokens"], data["cache_write_tokens"], data["cache_read_tokens"], data["output_tokens"]

    log_path = group_dir / "stderr.log"
    if not log_path.is_file():
        return None

    usage = _usage_from_log(log_path)
    input_tokens, cache_write_tokens, cache_read_tokens, output_tokens = usage
    tokens_path.write_text(json.dumps({
        "input_tokens": input_tokens,
        "cache_write_tokens": cache_write_tokens,
        "cache_read_tokens": cache_read_tokens,
        "output_tokens": output_tokens,
    }, indent=2))
    return usage


@dataclass(frozen=True)
class Pricing:
    prompt: float
    completion: float
    cache_read: float
    cache_write: float | None = None  # None -> billed at `prompt` rate


# Standard-tier (non-flex) list pricing per token, from openrouter.ai/api/v1/models
# (fetched 2026-10-23). DeepSeek's off-peak-UTC tier is used (see module docstring).
PRICING: dict[str, Pricing] = {
    "openai/gpt-6.1-sol": Pricing(prompt=0.000002, completion=0.00001, cache_read=0.0000001, cache_write=0.0000025),
    "openai/gpt-6-luna": Pricing(prompt=0.0000001, completion=0.0000005, cache_read=0.00000001, cache_write=0.000000125),
    "deepseek/deepseek-v4.1-flash-1017": Pricing(prompt=0.00000015, completion=0.0000006, cache_read=0.000000003),
    "z-ai/glm-5.3-flash": Pricing(prompt=0.00000015, completion=0.0000005, cache_read=0.00000003),
}


def sum_usage(batch_dir: Path) -> tuple[int, int, int, int]:
    input_tokens = cache_write_tokens = cache_read_tokens = output_tokens = 0
    missing: list[str] = []
    for group_dir in sorted(p for p in batch_dir.iterdir() if p.is_dir()):
        usage = group_usage(group_dir)
        if usage is None:
            missing.append(group_dir.name)
            continue
        it, cw, cr, ot = usage
        input_tokens += it
        cache_write_tokens += cw
        cache_read_tokens += cr
        output_tokens += ot
    if missing:
        print(
            f"warning: {len(missing)} group(s) had neither {USAGE_TOKENS_FILENAME} nor stderr.log "
            f"-- excluded from totals: {missing}",
            file=sys.stderr,
        )
    return input_tokens, cache_write_tokens, cache_read_tokens, output_tokens


def estimate(pricing: Pricing, input_tokens: int, cache_write_tokens: int, cache_read_tokens: int, output_tokens: int) -> float:
    cache_write_rate = pricing.cache_write if pricing.cache_write is not None else pricing.prompt
    uncached_input_tokens = max(0, input_tokens - cache_write_tokens - cache_read_tokens)
    return (
        uncached_input_tokens * pricing.prompt
        + cache_write_tokens * cache_write_rate
        + cache_read_tokens * pricing.cache_read
        + output_tokens * pricing.completion
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("batch_id")
    parser.add_argument("--model", required=True, choices=sorted(PRICING))
    args = parser.parse_args()

    batch_dir = RUNS_DIR / args.batch_id
    if not batch_dir.is_dir():
        raise SystemExit(f"no such batch: {batch_dir}")

    input_tokens, cache_write_tokens, cache_read_tokens, output_tokens = sum_usage(batch_dir)
    pricing = PRICING[args.model]
    cost = estimate(pricing, input_tokens, cache_write_tokens, cache_read_tokens, output_tokens)

    print(f"batch:              {args.batch_id}")
    print(f"model:              {args.model}")
    print(f"input_tokens:       {input_tokens:,}")
    print(f"cache_write_tokens: {cache_write_tokens:,}")
    print(f"cache_read_tokens:  {cache_read_tokens:,}")
    print(f"output_tokens:      {output_tokens:,}")
    print(f"estimated cost:     ${cost:.4f}")


if __name__ == "__main__":
    main()
