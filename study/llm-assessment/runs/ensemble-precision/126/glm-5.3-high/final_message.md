# Assessment

## Configuration under review

In the root module (instantiated as `module.runner` in `examples/runner-default/main.tf` via `source = "../../"`):

**Node — `aws_autoscaling_group.gitlab_runner_instance`** (`main.tf:188`):
- `launch_configuration = aws_launch_configuration.gitlab_runner_instance.name` (implicit dep)

**Target — `aws_iam_role_policy_attachment.docker_machine_cache_instance`** (`main.tf:297`):
- `role = aws_iam_role.instance.name`
- `policy_arn = local.bucket_policy` (the cache S3 policy from `module.cache.policy_arn` or `var.cache_bucket["policy"]`)

## Dependency analysis

**Existing ordering Terraform already enforces:**
- ASG → `aws_launch_configuration.gitlab_runner_instance` → `aws_iam_instance_profile.instance` → `aws_iam_role.instance` (via `iam_instance_profile` attribute reference, `main.tf:228`)
- ASG → launch config → `data.template_file.user_data` → `local.bucket_name` → `module.cache` bucket

So Terraform already guarantees the IAM role and instance profile exist before the ASG/launch configuration, and that the cache bucket exists before user data renders. There is **no path** from the ASG to the `docker_machine_cache_instance` attachment (it runs in parallel with the launch configuration after the role is created), and no `depends_on` exists anywhere in `main.tf`.

**Is the missing edge actually required?**

1. **ASG creation** never consults role policies — AWS validates only the launch configuration and subnets. The attachment is irrelevant to creating the ASG.
2. **Instance launch** requires only that the instance profile exists and contains the role — already guaranteed by the expressed chain above. Policy attachments are not a launch prerequisite.
3. **IAM semantics:** permissions are evaluated per API call. A policy attached to a role *after* an instance launches takes effect for that running instance within seconds — no relaunch needed. The runner agent gains S3 cache access as soon as the attachment completes.
4. **Boot-time behavior:** the user-data script (`template/gitlab-runner.tpl`) performs registration (SSM/GitLab API) and a dummy `docker-machine create --driver none` — none of it touches the S3 cache bucket. The cache policy is exercised only lazily, at job time, which is minutes after boot (yum update, package installs), while the attachment API call completes in seconds during the same apply.
5. ASG instances are replaced/scaled at arbitrary later times anyway; the attachment (long complete by then) applies dynamically.

## Conclusion

The only hard ordering requirements here — the IAM role and instance profile must exist before the launch configuration/ASG can launch instances, and the cache bucket must exist for the user data — are already expressed in the configuration through attribute references. The cache policy attachment is a dynamically-evaluated IAM permission change with no boot-time or launch-time consumer; it does not need to precede ASG creation or instance launch for correct creation or operation of the ASG. The reported "ordering requirement" is a speculative race that self-heals and has no concrete enforcement need.

Incorrect