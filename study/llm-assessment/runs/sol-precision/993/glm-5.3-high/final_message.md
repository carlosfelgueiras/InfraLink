I've now traced the complete picture. Let me summarize my assessment.

## Analysis

**The design of the module (root module, instantiated as `module "runner"` in `examples/runner-public`):**

1. `aws_ssm_parameter.runner_registration_token` (main.tf:85) is Terraform-managed (`enable_manage_gitlab_token` defaults to `true`). It is created with the placeholder value `"null"` and has `lifecycle { ignore_changes = ["value"] }` — the comment at main.tf:84 states the value is intentionally managed by the instance's user-data script.

2. The user-data script (rendered via `data.template_file.gitlab_runner` from `template/gitlab-runner.tpl`) implements a registration protocol at boot:
   - Line 29: reads the token with `aws ssm get-parameters --names "${secure_parameter_store_runner_token_key}"`
   - Lines 30–41: if the value is `"null"`, registers a new runner with GitLab and writes the real token back via `aws ssm put-parameter --overwrite`

3. The template gets the parameter name via `secure_parameter_store_runner_token_key = "${local.secure_parameter_store_runner_token_key}"` (main.tf:129) — a plain string computed from variables (`main.tf:14`), **not** a reference to the managed parameter.

**The ordering requirement is real:**

The protocol only works if the SSM parameter exists (initialized to `"null"`) *before* the instance boots. If the ASG launches first:
- user-data reads a missing parameter → token resolves to `"null"` → it registers a runner and creates the parameter with the real token,
- then Terraform creates `aws_ssm_parameter.runner_registration_token` with value `"null"` (the AWS provider issues PutParameter with overwrite), **clobbering the real token**,
- on the next instance replacement, user-data sees `"null"` again and registers a *new* runner — exactly the "missing-parameter or competing-creation race" described, producing duplicate/orphaned runners.

**Is the ordering currently expressed anywhere?** No:
- `aws_ssm_parameter.runner_registration_token` is referenced nowhere else in the module (verified by grep — only its own declaration).
- The SSM IAM policy (`policies/instance-secure-parameter-role-policy.json`) uses wildcard resources (`arn:aws:ssm:*`), so there's no transitive edge through IAM → instance profile → launch configuration.
- The chain `data.template_file.gitlab_runner` → `data.template_file.user_data` → `aws_launch_configuration` → `aws_autoscaling_group` therefore has **no edge** on the parameter, and Terraform can create the ASG (which immediately launches an instance) before the parameter in a fresh apply.

**Is the proposed fix sound?** Yes — referencing `aws_ssm_parameter.runner_registration_token.name` in the template vars would create the transitive ordering: parameter → template → user_data → launch configuration → ASG, ensuring the parameter is initialized before any instance boots. The template is exactly where the parameter's name is consumed, making it the correct expression point for this dependency.

The report accurately identifies both the concrete operational ordering requirement and the absence of any implicit or explicit dependency enforcing it in the configuration.

Correct