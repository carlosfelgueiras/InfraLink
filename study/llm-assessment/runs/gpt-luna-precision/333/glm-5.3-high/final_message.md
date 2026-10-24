## Assessment

**Configuration facts (verified in the snapshot):**

In `modules/fargate-profile/main.tf`:
- `aws_iam_role_policy_attachment.this` (lines 46–54) attaches `AmazonEKSFargatePodExecutionRolePolicy`, the CNI policy, and any `iam_role_additional_policies` to `aws_iam_role.this[0].name`.
- `aws_eks_fargate_profile.this` (lines 60–86) references only the role: `pod_execution_role_arn = var.create_iam_role ? aws_iam_role.this[0].arn : var.iam_role_arn`. It contains **no attribute reference** to the policy attachment resource and **no `depends_on`**. The root `module "fargate_profile"` call (`node_groups.tf` lines 192–218) adds no `depends_on` either, and the module's outputs create no such edge. The only shared connection between the two resources is their common dependency on `aws_iam_role.this`, so Terraform may create the profile before, or concurrently with, the policy attachments (e.g., under `-parallelism=1` the profile fully reaches `ACTIVE` first).

**Is a real ordering requirement present?**

- Yes. AWS documents the pod execution role *with* `AmazonEKSFargatePodExecutionRolePolicy` attached as a prerequisite: "Before you create a Fargate profile, you must create an IAM role with the AmazonEKSFargatePodExecutionRolePolicy" (EKS User Guide, pod execution role).
- The profile is not inert once created — Terraform's waiter blocks until the profile is `ACTIVE`, at which point "if a to-be-scheduled Pod matches any of the selectors in the Fargate profile, then that Pod is scheduled on Fargate." The kubelet on the Fargate infrastructure assumes the pod execution role at pod launch to pull ECR images, route logs, and (for IPv6 clusters) allocate pod IPs via the CNI policy. If the policies are not yet attached, those pods fail to start.
- The failure window is concrete, not hypothetical: pending matching pods exist in real uses of this module (e.g., the `examples/complete` profile selects `kube-system`/`k8s-app=kube-dns`, and the separate fargate module there selects all of `kube-system`, so pending CoreDNS pods are scheduled onto Fargate the moment the profile activates). Anything deployed later that depends on the profile also never transitively waits for the attachments.
- The codebase itself treats this exact class of requirement as real: in `modules/eks-managed-node-group/main.tf` (lines 249–254), the launch template explicitly uses `depends_on = [aws_security_group_rule.this, aws_iam_role_policy_attachment.this]` "to prevent premature access of ... policies" before compute starts hosting pods. The fargate profile module is missing the analogous edge.

**Conclusion:** The pod execution role must be made ready (policies attached) before the profile becomes active and starts placing pods on Fargate; that ordering is required by AWS's documented prerequisite and by the profile's immediate operational effect, and Terraform currently has no edge (implicit or explicit) enforcing it. Both diagnostic runs describe this same genuine missing dependency.

Correct