#!/usr/bin/env bash
# Stage 4: runs the opencode-based LLM precision assessment over each of the
# 5 samples from 03_generate_samples.sh, producing runs/<batch-id>/results.csv
# (plus one subdirectory per diagnostic id with the full per-configuration
# transcripts).
#
# Requires the `opencode` CLI installed and authenticated with its OWN
# OpenRouter credentials (separate from dependency-fixer's .env -- opencode
# manages its own auth; see opencode's docs). Costs real OpenRouter credits.
#
# Resumable: already-done (diagnostic, configuration) pairs are skipped unless
# --force is passed. Set JOBS to raise concurrency (default 4).
set -euo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../llm-assessment"

JOBS="${JOBS:-4}"

# "sample file (relative to ../recall_eval):batch-id" pairs.
SAMPLES=(
  "sample_30_merged_gpt_6_luna_atleast2of3.simplified.json:gpt-luna-precision"
  "sample_30_merged_glm_5.3_flash_atleast2of3.simplified.json:glm-precision"
  "sample_30_merged_deepseek_atleast2of3.simplified.json:deepseek-precision"
  "sample_30_gpt_6.1_sol_flex_effort_high_run1.simplified.json:sol-precision"
  "sample_30_union-merged-atleast2of3-luna-deepseek-glm.simplified.json:ensemble-precision"
)

for entry in "${SAMPLES[@]}"; do
  sample="${entry%%:*}"
  batch="${entry##*:}"
  echo "=== $batch ==="
  python3 run_assessment.py \
    --samples "../recall_eval/$sample" \
    --configs configs.json \
    --rules rules.md \
    --batch-id "$batch" \
    --jobs "$JOBS"
  echo
done
