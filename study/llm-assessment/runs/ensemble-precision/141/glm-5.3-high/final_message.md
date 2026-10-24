## Assessment

**Reported dependency:** `aws_launch_configuration.gitlab_runner_instance` → `aws_iam_role_policy_attachment.ssm` (both in the root module instantiated as `module.runner` by `examples/runner-docker`).

### 1. Is the dependency currently expressed? — No.

The launch configuration (`main.tf:221-235`) references only:
- `aws_security_group.runner.id`, `aws_key_pair.key.key_name`, `data.aws_ami.runner.id`, `data.template_file.user_data.rendered`, and `aws_iam_instance_profile.instance.name`.

There is no attribute reference to the SSM attachment and no `depends_on` in the module (grep confirms `depends_on` appears only in the examples' `key.tf` files). The ASG (`main.tf:188-203`) likewise depends only on the launch configuration. Both the LC branch (`role` → `instance profile` → `LC`) and the attachment branch (`role`/`aws_iam_policy.ssm` → `attachment`) hang off `aws_iam_role.instance` in parallel, so Terraform has no edge forcing the attachment to complete before the LC/ASG/instance launch.

### 2. Is there a real ordering requirement? — Yes.

- In this example `enable_manage_gitlab_token` defaults to `true` (variables.tf:368-371, not overridden), so `aws_iam_policy.ssm` + `aws_iam_role_policy_attachment.ssm` are created, and `runners_token` defaults to `__REPLACED_BY_USER_DATA__`, activating the SSM logic in the bootstrap script.
- The user-data script (`template/gitlab-runner.tpl:29,40`) runs `aws ssm get-parameters --with-decryption` and, on first boot, registers the runner and runs `aws ssm put-parameter`. Under `#!/bin/bash -e`, an AccessDenied aborts the bootstrap, and without the token the runner cannot register at all.
- Those exact permissions (`ssm:GetParameters`, `ssm:PutParameter`) are granted **only** by `policies/instance-secure-parameter-role-policy.json` via `aws_iam_role_policy_attachment.ssm`, attached to `aws_iam_role.instance` — the role the LC assigns through `aws_iam_instance_profile.instance`. The instance role's other attached policies (docker-machine EC2 policy, cache bucket policy, service-linked-role policy) grant no SSM permissions.
- The ASG (`min_size = 1, desired = 1`) launches the runner agent instance immediately once the LC exists, so instance bootstrap happens within the same apply and can race the attachment. Since the ASG depends on the LC, adding the dependency on the LC is precisely the correct enforcement point: attachment → LC → ASG → instance boot.

The launch configuration waits only on the instance profile (which waits only on the role), not on the SSM policy attachment, so an instance can boot and run its user-data before the SSM policy is attached — exactly the unenforced ordering gap the report describes. Both diagnostic runs describe the same requirement accurately.

### Verdict

The report is **Correct**: the runner agent instance launched from this launch configuration requires the SSM policy to be attached to its role before its user-data bootstrap (SSM get/put of the registration token) can succeed, and this ordering is not expressed in the configuration.

Correct