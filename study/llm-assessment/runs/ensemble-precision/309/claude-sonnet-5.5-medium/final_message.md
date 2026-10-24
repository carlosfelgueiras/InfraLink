The lambda references the output through a local, and Terraform resolves locals, so an implicit dependency already exists. The report is therefore incorrect.

The reference is at `modules/runners/scale-up.tf`. `JOB_RETRY_CONFIG = jsonencode(local.job_retry_config)` uses `local.job_retry_config`. That local reads `module.job_retry[0].job_retry_check_queue.url` (line 7). Terraform follows references through locals, so `aws_lambda_function.scale_up` already depends on that module output. The queue is created before the lambda, and the lambda is updated if the URL changes.

The report's claim that the reference is "hidden behind a local" is wrong. The dependency graph tool may simply not show edges that pass through locals.

Incorrect