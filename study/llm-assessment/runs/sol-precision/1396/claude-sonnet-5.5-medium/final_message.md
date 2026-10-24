The report is correct.

- **What reads the parameter:** At boot, the runner startup scripts (`templates/start-runner.sh` and `start-runner-osx.sh`) read `<ssm_config_path>/run_as` from SSM. They use it to pick the user for `chown`, `config.sh` and `run.sh`.
- **What the pool does:** `aws_scheduler_schedule.pool` triggers the pool lambda on a schedule, and that lambda launches EC2 runners.
- **Where Terraform's ordering falls short:** `aws_ssm_parameter.runner_config_run_as` is created in `runner-config.tf`. The pool module (`pool.tf`) only gets `ssm_config_path` as a plain string, built from `var.ssm_paths`. Nothing in that call references the parameter, and there is no `depends_on`. Terraform can therefore create the schedule, and the pool can start launching runners, before the parameter exists.
- **What goes wrong if it races:** A runner that boots before the parameter exists gets an empty `run_as`. It then falls back to `ec2-user`, even if `runner_as_root` or `runner_run_as` was configured.

The race is narrow, but it comes from a real ordering requirement that Terraform isn't told about. A `depends_on` on the parameter in the pool module call would express it.

Correct