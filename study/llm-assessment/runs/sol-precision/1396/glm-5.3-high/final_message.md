## Assessment

**Reported dependency:** `module.pool:resource.aws_scheduler_schedule.pool` → `aws_ssm_parameter.runner_config_run_as` (in `modules/runners`)

### What I found

**1. The schedule does not consume the parameter in any way.**
In `modules/runners/pool/main.tf` (lines 220-241), `aws_scheduler_schedule.pool` references only the schedule group, the pool lambda ARN, and the scheduler IAM role. Its sole function is to periodically invoke the pool lambda. The `run_as` parameter is never read by the schedule, the lambda, or anything else in the pool module — the pool module receives only path *strings* (`ssm_config_path`, built from `var.ssm_paths` in `modules/runners/pool.tf:62`), never a reference to `aws_ssm_parameter.runner_config_run_as`.

**2. The actual consumer reads it at runtime, with a documented fallback.**
The real consumer of `run_as` is the runner instance's bootstrap script (`modules/runners/templates/start-runner.sh:162-166, 213-216`), which fetches parameters by path at boot and explicitly tolerates a missing `run_as`:

```sh
if [ -z "$run_as" ]; then
  echo "No user specified, using default ec2-user account"
  run_as="ec2-user"
fi
```

The same fallback exists in `start-runner.ps1` (line 124-126) and `start-runner-osx.sh` (line 123-125). `ec2-user` is exactly the module's default value of `runner_run_as`, so with default configuration a missing parameter has no effect at all. Runner creation does not fail without the parameter.

**3. The module deliberately treats config-path parameters as runtime-read values, not creation-order dependencies.**
No `depends_on` exists anywhere in `modules/runners`, and none of the sibling config parameters (`agent_mode`, `token_path`, `enable_jit_config`, etc.) are ordered against the pool schedule, pool lambda, or the scale-up lambda — all of which can equally launch runners. Where a *hard* ordering requirement genuinely exists, the module does express it: `aws_launch_template.runner` uses `image_id = "resolve:ssm:..."` referencing `aws_ssm_parameter.runner_ami_id[0].arn` (`main.tf:219`), creating a real implicit dependency (which the pool module inherits transitively via `config.runner.launch_template`). The critical runtime dependency — the per-instance registration token — is handled by an explicit wait loop in the user-data (`start-runner.sh:203-208`). This shows the config-path parameters are intentionally left as runtime reads with graceful defaults.

**4. No concrete ordering requirement from the parameter to the schedule.**
The claim's failure mode requires all of: (a) initial apply, (b) the schedule being created and firing its first tick before a dependency-free one-second SSM parameter write completes — even though the schedule sits at the end of a long chain (schedule group → scheduler IAM role → lambda → schedule), and (c) a non-default `runner_run_as` for the fallback to differ from the parameter value. Even then, the effect is limited to runners launched in that tiny window, and the next schedule tick self-corrects. A `depends_on` would only reorder creation within a single apply; it cannot enforce the claimed runtime invariant ("the parameter exists whenever the schedule fires"), which is a boot-time concern of the EC2 instances, not of the schedule resource.

### Conclusion

The two resources are related (pool-launched runners eventually read `run_as`), but the schedule itself neither consumes the parameter nor mis-operates without it, and the actual consumer explicitly handles the parameter's absence with a default matching the module's own default. There is no concrete ordering requirement from `aws_ssm_parameter.runner_config_run_as` to `aws_scheduler_schedule.pool` that Terraform needs to enforce.

Incorrect