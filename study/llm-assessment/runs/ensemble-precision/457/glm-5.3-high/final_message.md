## Assessment

**Resources involved (both in the module entrypoint, `workers.tf`):**
- Source: `aws_autoscaling_group.workers` (line 3) — self-managed workers ASG (launch-configuration based)
- Target: `aws_iam_role_policy_attachment.workers_AmazonEC2ContainerRegistryReadOnly` (line 398) — attaches the ECR read-only managed policy to `aws_iam_role.workers`

**Dependency graph as expressed:** The ASG → `aws_launch_configuration.workers` (`launch_configuration` attribute) → `aws_iam_instance_profile.workers` (`iam_instance_profile` attribute) → `aws_iam_role.workers` (via `local.default_iam_role_id`). The attachment also depends only on `aws_iam_role.workers`. Both branches hang off the role, and **no path connects the ASG to the attachment** — the reported dependency is indeed not expressed anywhere (the attachment IDs are only referenced by `data.null_data_source.node_groups` in `node_groups.tf`, which feeds only the managed node groups module, not the ASG).

**Is the ordering actually required?** No:

1. **No API requirement.** EC2 Auto Scaling / `CreateLaunchConfiguration` / `RunInstances` never validate the instance role's *policies* — only that the instance profile/role exists (which is expressed). Unlike EKS *managed* node groups, where the EKS API rejects node-group creation if the node role lacks the required policies, a self-managed ASG is created and launches instances successfully regardless of the attachment. Notably, the module authors *did* enforce this ordering for managed node groups (the `null_data_source` hack in `node_groups.tf`, commented "Removes race conditions") precisely because that API validates it — and deliberately did not for the ASGs.

2. **IAM policy attachments are dynamic.** Attaching a policy to the role takes effect for already-running instances automatically (permissions are evaluated per API call using the role's current policies). No re-launch is needed.

3. **The failure mode is transient and self-healing.** In a single apply, the attachment is created within seconds of the role, while instances take a minute or more to boot before kubelet's first image pull; and even if a pull fails, kubelet retries (`ImagePullBackOff`) and succeeds once the attachment lands. Nothing gets permanently stuck, and the cluster converges to correct operation regardless of ordering. A `depends_on` would not "enforce" readiness anyway (IAM eventual consistency, and the ASG resource doesn't wait for instance boot).

So while the two resources are related and the ECR policy is genuinely needed for the nodes' operation *eventually*, there is no concrete ordering requirement that the attachment exist *before* the ASG is created — only a benign, self-healing race that AWS imposes no constraint on, and which the configuration intentionally (and consistently, for both `workers` and `workers_launch_template`) does not model.

Incorrect