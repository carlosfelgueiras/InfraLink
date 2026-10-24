The reported missing dependency is **Correct**.

### Analysis
1. **Configuration & Dependency Graph:**
   - `:resource.aws_ssm_parameter.runner_config_run_as` (declared in `modules/runners/runner-config.tf`) creates the SSM parameter `${var.ssm_paths.root}/${var.ssm_paths.config}/run_as` holding the user account (`root` or `var.runner_run_as`) under which the GitHub Actions runner service should execute.
   - `module.pool` (declared in `modules/runners/pool.tf`) receives `ssm_config_path = "${var.ssm_paths.root}/${var.ssm_paths.config}"` as a plain interpolated string and `launch_template = aws_launch_template.runner`. Neither `module.pool` nor `aws_launch_template.runner` references `aws_ssm_parameter.runner_config_run_as` (implicitly or via `depends_on`).
   - Inside `module.pool` (`modules/runners/pool/main.tf`), `resource.aws_scheduler_schedule.pool` creates an active EventBridge schedule targeting `aws_lambda_function.pool`.

2. **Operational Requirement:**
   - As soon as `module.pool:resource.aws_scheduler_schedule.pool` is created, it can trigger the pool Lambda function to launch EC2 runner instances.
   - During instance startup (`start-runner.sh`, `start-runner.ps1`, `start-runner-osx.sh`), the bootstrap script queries SSM Parameter Store at `$ssm_config_path` (via `aws ssm get-parameters-by-path`) to retrieve `$ssm_config_path/run_as` and configure/start the runner under the specified user.
   - Because Terraform has no dependency link between `module.pool:resource.aws_scheduler_schedule.pool` and `:resource.aws_ssm_parameter.runner_config_run_as`, the schedule can invoke the pool Lambda and launch runner instances before the `run_as` SSM parameter exists.

Correct