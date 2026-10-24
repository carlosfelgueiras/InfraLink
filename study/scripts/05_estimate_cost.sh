#!/usr/bin/env bash
# Stage 5: estimates OpenRouter credit cost of the 10 individual runs from
# 01_run_experiments.sh. The 3 merged batches and the union/ensemble batch
# cost nothing extra -- merge_runs.py only recombines data already fetched
# in stage 1, it makes no new API calls.
#
# This is an ESTIMATE from logged token counts x published list pricing, not
# the actual billed amount -- see estimate_cost.py's own docstring for the
# caveats (no real per-request cost is logged; gpt-6.1-sol-flex's number is an
# upper bound since flex's discount isn't exposed by OpenRouter's pricing API).
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../recall_eval"

# "batch-id:openrouter model slug" pairs.
RUNS=(
  "final-gpt-6-luna-effort-high-run1:openai/gpt-6-luna"
  "final-gpt-6-luna-effort-high-run2:openai/gpt-6-luna"
  "final-gpt-6-luna-effort-high-run3:openai/gpt-6-luna"
  "final-glm-5.3-flash-effort-high-run1:z-ai/glm-5.3-flash"
  "final-glm-5.3-flash-effort-high-run2:z-ai/glm-5.3-flash"
  "final-glm-5.3-flash-effort-high-run3:z-ai/glm-5.3-flash"
  "final-deepseek-v4.1-flash-1017-effort-high-run1:deepseek/deepseek-v4.1-flash-1017"
  "final-deepseek-v4.1-flash-1017-effort-high-run2:deepseek/deepseek-v4.1-flash-1017"
  "final-deepseek-v4.1-flash-1017-effort-high-run3:deepseek/deepseek-v4.1-flash-1017"
  "final-gpt-6.1-sol-flex-effort-high-run1:openai/gpt-6.1-sol"
)

for entry in "${RUNS[@]}"; do
  batch="${entry%%:*}"
  model="${entry##*:}"
  python3 estimate_cost.py "$batch" --model "$model"
  echo
done
