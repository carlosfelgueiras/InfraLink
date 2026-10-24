#!/usr/bin/env bash
# Stage 2: scores every batch from 01_run_experiments.sh against the
# dataset's ground-truth (holder, target) pairs and writes one CSV per batch.
# Cheap and fast -- no API calls, just reads eval_runs/.
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../recall_eval"

# "batch-id:csv filename" pairs, plain array (not an associative array -- those
# don't behave consistently across every shell this might get sourced from).
BATCHES=(
  "final-gpt-6-luna-effort-high-run1:scores_final_gpt_6_luna_effort_high_run1.csv"
  "final-gpt-6-luna-effort-high-run2:scores_final_gpt_6_luna_effort_high_run2.csv"
  "final-gpt-6-luna-effort-high-run3:scores_final_gpt_6_luna_effort_high_run3.csv"
  "final-glm-5.3-flash-effort-high-run1:scores_final_glm_effort_high_run1.csv"
  "final-glm-5.3-flash-effort-high-run2:scores_final_glm_effort_high_run2.csv"
  "final-glm-5.3-flash-effort-high-run3:scores_final_glm_effort_high_run3.csv"
  "final-deepseek-v4.1-flash-1017-effort-high-run1:scores_final_deepseek_effort_high_run1.csv"
  "final-deepseek-v4.1-flash-1017-effort-high-run2:scores_final_deepseek_effort_high_run2.csv"
  "final-deepseek-v4.1-flash-1017-effort-high-run3:scores_final_deepseek_effort_high_run3.csv"
  "final-gpt-6.1-sol-flex-effort-high-run1:scores_final_gpt_6.1_sol_flex_effort_high_run1.csv"
  "merged-gpt-6-luna-atleast2of3:scores_merged_gpt_6_luna_atleast2of3.csv"
  "merged-glm-5.3-flash-atleast2of3:scores_merged_glm_atleast2of3.csv"
  "merged-deepseek-v4.1-flash-1017-atleast2of3:scores_merged_deepseek_atleast2of3.csv"
  "union-merged-atleast2of3-luna-deepseek-glm:scores_union_merged_atleast2of3.csv"
)

for entry in "${BATCHES[@]}"; do
  batch="${entry%%:*}"
  csv="${entry##*:}"
  echo "=== $batch ==="
  python3 score_eval.py --batch-id "$batch" --csv "$csv"
  echo
done
