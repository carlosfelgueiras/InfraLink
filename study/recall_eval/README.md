# Recall study — Stage 1 (run harness)

Runs `dependency-fixer`'s agentic check against every `(repo, parent_sha,
module_dir)` group implied by
`dataset/missing_dependency_mining/results/all_trustworthy.json`, and saves
everything needed to grade it later (Stage 2, not implemented yet).

**Not run yet.** Only syntax-checked.

## Design decisions (see conversation for full reasoning)

- **One run per group, no repeats.** Early idea-paper pass, kept cheap on
  purpose. A single run is a noisy point estimate of recall, not a precise
  one — say so wherever these numbers get reported.
- **`module_dir` is the project root dependency-fixer runs against**, not the
  repo root. The dataset's `holder_address`/`added_targets` are bare
  `<type>.<name>` strings (no module-call prefix) precisely because the
  mining pipeline itself analyzed each `module_dir` in isolation — so this
  isn't an approximation, it's matching the exact scope the ground truth was
  produced against. Address comparison in Stage 2 should just be
  `f":resource.{address}"`.
- **Full repo checked out, not just `module_dir`.** Avoids a real failure
  mode: a module's own relative `source = "../sibling"` references resolving
  outside `module_dir` if only that subtree were on disk.
- **No re-cloning.** `dataset/missing_dependency_mining/repos/<owner>__<repo>`
  already holds full (non-shallow) clones made by the mining pipeline itself.
  Verified: all 15 distinct repos referenced by `all_trustworthy.json` are
  already there. This script only adds a `git worktree` per distinct
  `(repo, resolved parent_sha)` on top of that existing clone.
- **Checkout unit vs. invocation unit**: one worktree per `(repo, parent_sha)`
  (shared across every `module_dir` that references that commit); one
  `dependency-fixer` invocation per `(repo, parent_sha, module_dir)`.
- **Resumable**: a group is skipped if its output dir already has an
  `exit_code` file, unless `--force`. Safe to stop/extend a batch.
- **Per-run timeout** (`--timeout-seconds`, default 600s) so one hung case
  (e.g. a tool-call loop against a flaky backend) can't stall the batch —
  recorded as `exit_code = "TIMEOUT"` rather than raising.

## Output layout

```
eval_runs/<batch-id>/<repo>__<resolved_sha[:12]>__<module_dir-slug>/
  meta.json            # repo, parent_sha, resolved_sha, module_dir, profile,
                        # effort, temperature, and the full matching dataset rows
  stdout.json          # dependency-fixer's --json diagnostics output
  stderr.log           # full --log-level DEBUG output (tool calls, chat
                        # trajectory, live stream events) for manual inspection
  exit_code            # int, or "TIMEOUT" — presence marks the group done
  duration_seconds
```

`worktrees/<repo>/<resolved_sha[:12]>/` holds the actual git worktrees (not
committed — scratch space, safe to delete and will be recreated on demand).

## Usage

```bash
# See the plan without checking anything out or spending anything
python3 run_eval.py --profile bedrock-claude-sonnet --dry-run

# Cheap pilot: first 5 groups only
python3 run_eval.py --profile bedrock-claude-sonnet --limit 5

# One repo, for debugging
python3 run_eval.py --profile bedrock-claude-sonnet --repo Azure__terraform-azurerm-caf-enterprise-scale

# Full batch
python3 run_eval.py --profile bedrock-claude-sonnet --batch-id 2026-10-19
```

## Not yet implemented

Stage 2 (scoring): load each group's `stdout.json`, filter to
`category == "missing"` diagnostics, check each dataset
`(holder_address, target)` pair for an exact `(node, target)` match, report
recall overall and broken down by resource-type pair / repo.
