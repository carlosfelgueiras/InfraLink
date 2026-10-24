#!/usr/bin/env bash
# Stage 1: runs dependency-fixer over the full mined dataset for the study's
# 10 "final" runs -- 3x each of gpt-6-luna / glm-5.3-flash /
# deepseek-v4.1-flash-1017 at high reasoning effort, plus 1x gpt-6.1-sol-flex
# at high effort -- then builds each small model's per-model ">=2-of-3 runs
# agree" merge, and the cross-model union of those 3 merges (the "ensemble").
#
# Costs real OpenRouter credits (roughly $45-50 total for all 10 runs at the
# prices in effect when this was written -- see 05_estimate_cost.sh) and can
# take hours. Safe to interrupt and re-run: run_eval.py skips any group that
# already has a result, so this script is idempotent.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../recall_eval"

for i in 1 2 3; do
  echo "=== gpt-6-luna, effort high, run$i ==="
  python3 run_eval.py --profile openrouter-gpt-6-luna --effort high \
    --batch-id "final-gpt-6-luna-effort-high-run$i"
done

for i in 1 2 3; do
  echo "=== glm-5.3-flash, effort high, run$i ==="
  python3 run_eval.py --profile openrouter-glm-5.3-flash --effort high \
    --batch-id "final-glm-5.3-flash-effort-high-run$i"
done

for i in 1 2 3; do
  echo "=== deepseek-v4.1-flash-1017, effort high, run$i ==="
  python3 run_eval.py --profile openrouter-deepseek-v4.1-flash-1017 --effort high \
    --batch-id "final-deepseek-v4.1-flash-1017-effort-high-run$i"
done

echo "=== gpt-6.1-sol-flex, effort high, run1 ==="
python3 run_eval.py --profile openrouter-gpt-6.1-sol-flex --effort high \
  --batch-id final-gpt-6.1-sol-flex-effort-high-run1

echo "=== merging each small model's 3 runs (kept only when >=2 of 3 agree) ==="
python3 merge_runs.py --out-batch-id merged-gpt-6-luna-atleast2of3 --min-runs 2 \
  final-gpt-6-luna-effort-high-run1 final-gpt-6-luna-effort-high-run2 final-gpt-6-luna-effort-high-run3
python3 merge_runs.py --out-batch-id merged-glm-5.3-flash-atleast2of3 --min-runs 2 \
  final-glm-5.3-flash-effort-high-run1 final-glm-5.3-flash-effort-high-run2 final-glm-5.3-flash-effort-high-run3
python3 merge_runs.py --out-batch-id merged-deepseek-v4.1-flash-1017-atleast2of3 --min-runs 2 \
  final-deepseek-v4.1-flash-1017-effort-high-run1 final-deepseek-v4.1-flash-1017-effort-high-run2 final-deepseek-v4.1-flash-1017-effort-high-run3

echo "=== ensemble: union of the 3 merged (>=2-of-3) results ==="
python3 merge_runs.py --out-batch-id union-merged-atleast2of3-luna-deepseek-glm --min-runs 1 \
  merged-gpt-6-luna-atleast2of3 merged-deepseek-v4.1-flash-1017-atleast2of3 merged-glm-5.3-flash-atleast2of3

echo "all runs complete."
