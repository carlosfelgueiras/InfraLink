## Assessment

**Reported missing dependency:** `modules/runners` → `aws_lambda_function.scale_up` should depend on `module.job_retry:output.job_retry_check_queue` (the job-retry SQS check queue).

### What the configuration actually does

In `modules/runners/scale-up.tf`:

- **Lines 1–9** define a local whose value embeds the module output:
  ```hcl
  locals {
    job_retry_config = local.job_retry_enabled ? {
      ...
      queueUrl = module.job_retry[0].job_retry_check_queue.url
    } : {}
  }
  ```
- **Line 67** uses that local in a direct attribute of the scale-up lambda:
  ```hcl
  JOB_RETRY_CONFIG = jsonencode(local.job_retry_config)
  ```

And in `modules/runners/job-retry/outputs.tf` (lines 9–11), the output `job_retry_check_queue` is `aws_sqs_queue.job_retry_check_queue`.

### Why the reported "missing dependency" is not missing

Terraform does **not** treat locals as opaque values that hide references. Local values are first-class nodes in Terraform's plan/apply graph (see `NodeLocal` in `hashicorp/terraform` `internal/terraform/node_local.go`, which implements both `GraphNodeReferencer` — the local depends on everything its expression references, here `module.job_retry[0].job_retry_check_queue.url` — and `GraphNodeReferenceable` — resources referencing the local depend on it). Terraform's `ReferenceTransformer` wires these edges, so the reference chain is fully expressed:

`aws_lambda_function.scale_up` → `local.job_retry_config` → `module.job_retry[0].job_retry_check_queue` → `aws_sqs_queue.job_retry_check_queue`

Consequently:

1. **Apply ordering is enforced.** The SQS queue `url` is a computed attribute ("known after apply"). When job retry is enabled, `JOB_RETRY_CONFIG` is unknown at plan time, so Terraform defers creation of `aws_lambda_function.scale_up` until `module.job_retry[0].aws_sqs_queue.job_retry_check_queue` is created — the exact ordering the report claims is missing.
2. **Update propagation works.** If the queue URL changes, the local's value changes, `JOB_RETRY_CONFIG` changes, and the lambda is updated in place. The report's claim that the function "would not be updated when the queue URL changes" is incorrect.
3. **Disabled case is moot.** When `var.job_retry.enable` is false, `module.job_retry` has `count = 0` and `local.job_retry_config = {}` — there is no queue to order against.

The diagnostic tool's graph simply failed to traverse the local, but Terraform itself has complete information to enforce the ordering. Adding `depends_on = [module.job_retry]` to the scale-up lambda would be redundant — the dependency is already expressed as an implicit (attribute-reference) dependency through the local.

The report is therefore incorrect: the required ordering is already expressed in the configuration.

Incorrect