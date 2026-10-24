# Reviewer scripts

Five scripts, run in order, reproduce the study's recall numbers, cost
estimate, and LLM-based precision assessment from scratch. Each wraps the
underlying Python scripts in `../recall_eval/` and `../llm-assessment/` with
the exact arguments and naming used to produce this study's results.

All scripts `cd` to the right directory on their own — run them from
anywhere, e.g. `./01_run_experiments.sh` or `bash 01_run_experiments.sh`.

## Prerequisites

- Python deps installed for `dependency-fixer` itself (`uv sync` from the repo
  root), plus an `.env` with `OPENROUTER_API_KEY` set (scripts 1 and 5 use
  OpenRouter via `dependency-fixer`'s own `--agentic-profile` backends).
- For script 4 only: the [`opencode`](https://opencode.ai) CLI installed and
  authenticated with **its own** OpenRouter credentials (opencode manages its
  own auth, independent of `dependency-fixer`'s `.env`).
- Scripts 1 and 4 call paid APIs and will spend real money. Scripts 2, 3, and
  5 are local-only (no network calls) and free.

## 1. `01_run_experiments.sh` — run the tool over the dataset

Runs `dependency-fixer`'s agentic check against every `(repo, parent_sha,
module_dir)` group in `dataset/missing_dependency_mining/results/all_trustworthy.json`,
for the study's 10 "final" configurations:

- 3 runs each of `gpt-6-luna`, `glm-5.3-flash`, and `deepseek-v4.1-flash-1017`
  (all at `--effort high`)
- 1 run of `gpt-6.1-sol-flex` (also at `--effort high`)

Then builds, from those: each small model's **merged** result (a diagnostic
is kept only if it's reported by at least 2 of that model's 3 runs — a
noise-reduction/voting filter), and the **ensemble**: the union of the 3
merged results across models.

Results land under `../recall_eval/eval_runs/<batch-id>/`, one subdirectory
per `(repo, commit, module_dir)` group, each holding `meta.json`,
`stdout.json` (the diagnostics), `stderr.log`, `exit_code`, and
`duration_seconds`.

**Cost & time**: real OpenRouter spend (roughly $45-50 total at the prices in
effect when this was written — see script 5's output for current figures)
and can take a few hours. **Resumable**: safe to interrupt and re-run — any
group that already has a result is skipped, so a partial run just picks up
where it left off.

## 2. `02_score_recall.sh` — get the recall results

Grades every batch from script 1 (all 10 raw runs + the 3 merged results +
the 1 ensemble result, 14 batches total) against the dataset's ground-truth
`(holder, target)` pairs. Prints a hit/miss/reversed/error breakdown and the
overall recall for each batch, and writes a per-pair CSV
(`../recall_eval/scores_*.csv`) for each one.

**Cost & time**: free, instant — reads only what script 1 already wrote, no
API calls.

## 3. `03_generate_samples.sh` — build the precision-review samples

For the 3 small-model merged results, the `gpt-6.1-sol-flex` run, and the
ensemble result (5 batches), this:

1. Flattens every `"missing"`-category diagnostic the batch produced into one
   JSON file, with context (repo/commit/module_dir) attached
   (`../recall_eval/diagnostics_*.json`).
2. Draws a reproducible random sample of 30 of them (fixed seed, 42)
   (`sample_30_*.json`).
3. Writes a simplified version of that sample — just `id`/`node`/`target`/
   `message`/`github_url` — for the judge in script 4 to work from
   (`sample_30_*.simplified.json`).

**Cost & time**: free, instant, local only.

## 4. `04_run_precision_assessment.sh` — run the LLM-based precision assessment

For each of the 5 samples from script 3, runs one fresh, sandboxed `opencode`
session per judge configuration (defined in `../llm-assessment/configs.json`,
currently `claude-sonnet-5.5-medium`, `gemini-4-argon-medium`, and
`glm-5.3-high`) against a pristine `git archive` snapshot of the exact
commit the diagnostic was produced against (no `.git` directory, so the judge
can't see the repo's later history — which for a mined diagnostic could
include the very commit that added the missing dependency, an answer leak).
Each judge reads the rules in `../llm-assessment/rules.md` and renders a
Correct/Incorrect verdict from its final message.

Results land under `../llm-assessment/runs/<batch-id>/`:
`results.csv` (one row per diagnostic x configuration, with the verdict) plus
one subdirectory per diagnostic id holding each configuration's full
transcript (`prompt.md`, `final_message.md`, `result.json`, `events.jsonl`,
etc. — `events.jsonl` is gitignored, see below).

Batch-ids used (so results line up with what's already in this repo):
`gpt-luna-precision`, `glm-precision`, `deepseek-precision`, `sol-precision`,
`ensemble-precision`.

**Cost & time**: real OpenRouter spend (opencode's own credentials) and the
slowest stage — 30 diagnostics x 5 samples x 3 judge configurations = 450
sandboxed agent sessions. Set `JOBS=<n>` (default 4) to raise concurrency,
e.g. `JOBS=8 ./04_run_precision_assessment.sh`. **Resumable**: already-judged
(diagnostic, configuration) pairs are skipped unless `--force` is added to
the underlying `run_assessment.py` call.

**A caution if re-running this against an existing `llm-assessment/runs/`
directory rather than a fresh clone**: script 3 assigns each diagnostic in a
batch a sequential id when it collects it, in iteration order. If you rerun
script 3 after the underlying data changed in a way that changes which
diagnostics get collected (e.g. a differently-filtered or re-ordered
collection), the same id can end up pointing at a different diagnostic than
it did before — desyncing it from any *already-computed* `runs/<batch-id>/<id>/`
results from an earlier script-3/4 pass. This is a non-issue on a clean,
from-scratch run (scripts 3 and 4 always see consistent ids within that one
run), but worth knowing if you're iterating on scripts 3/4 against
already-collected results rather than starting over.

## 5. `05_estimate_cost.sh` — cost estimate

Estimates the OpenRouter credit cost of the 10 paid runs from script 1, from
each run's logged per-request token usage (cached per group into a small,
PII-free `usage_tokens.json` the first time it's read, so this works even
once the much larger raw `stderr.log` files are stripped out of a release)
multiplied by each model's published OpenRouter list pricing. The 3 merged
batches and the ensemble batch cost nothing extra — `merge_runs.py` only
recombines data script 1 already fetched, no new API calls.

This is an **estimate**, not the actual billed amount — see
`../recall_eval/estimate_cost.py`'s docstring for the specific caveats
(no per-request cost is ever logged by OpenRouter for these requests;
DeepSeek's time-of-day pricing tiers are approximated with the off-peak rate;
`gpt-6.1-sol-flex`'s number is an upper bound, since flex's discount off
standard pricing isn't exposed by OpenRouter's pricing API).

**Cost & time**: free, instant, local only.
