#!/usr/bin/env bash
# Stage 3: for each small model's merged (>=2-of-3) result, the gpt-6.1-sol-flex
# run, and the cross-model ensemble, flattens all "missing"-category
# diagnostics into one file, draws a reproducible random sample of 30
# (seed=42), and writes a simplified (id/node/target/message/github_url)
# version of that sample for the opencode-based precision assessment
# (04_run_precision_assessment.sh).
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../recall_eval"

# "batch-id:output file label" pairs.
BATCHES=(
  "merged-gpt-6-luna-atleast2of3:merged_gpt_6_luna_atleast2of3"
  "merged-glm-5.3-flash-atleast2of3:merged_glm_5.3_flash_atleast2of3"
  "merged-deepseek-v4.1-flash-1017-atleast2of3:merged_deepseek_atleast2of3"
  "final-gpt-6.1-sol-flex-effort-high-run1:gpt_6.1_sol_flex_effort_high_run1"
  "union-merged-atleast2of3-luna-deepseek-glm:union-merged-atleast2of3-luna-deepseek-glm"
)

for entry in "${BATCHES[@]}"; do
  batch="${entry%%:*}"
  label="${entry##*:}"
  echo "=== $batch ==="
  python3 collect_diagnostics.py --batch-id "$batch" --category missing \
    --out "diagnostics_${label}.json"
  python3 sample_diagnostics.py --in "diagnostics_${label}.json" --n 30 --seed 42 \
    --out "sample_30_${label}.json"
  python3 simplify_diagnostics.py --in "sample_30_${label}.json" \
    --out "sample_30_${label}.simplified.json"
  echo
done
