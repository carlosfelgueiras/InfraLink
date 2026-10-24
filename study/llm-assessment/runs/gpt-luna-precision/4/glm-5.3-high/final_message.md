## Analysis

**The reported pair (both runs describe the same dependency):**
- **Source:** `aws_instance.bootstrap_node` — `terraform-aws/masters.tf:117-136`
- **Target:** `aws_iam_role_policy.elasticsearch` — `terraform-aws/iam.tf:18-22` (inline policy granting `ec2:DescribeInstances` on `aws_iam_role.elasticsearch`)

**Graph facts (confirmed):** The instance's only IAM reference is `iam_instance_profile = aws_iam_instance_profile.elasticsearch.id`, and the profile references `aws_iam_role.elasticsearch.name` — the *role*, not its inline policy. The instance has no `depends_on`. So the edge is indeed absent from the graph — the `aws_iam_role_policy` resources are siblings of the profile, both hanging off the role alone.

**But is the ordering actually required?**

1. **Creation time:** `RunInstances` needs only the instance profile (and its role) to exist — AWS does not evaluate the role's permission policies at launch. The instance can be created correctly without the discovery policy attached; the profile dependency is already expressed.

2. **Operation time — the bootstrap script tolerates a late-attached policy by design.** The bootstrap node's user data (`templates/user_data.sh:5-29`) calls `aws ec2 describe-instances` inside a `while true … sleep 5` poll loop that by design waits many minutes for all master instances (via the ASG, which the instance transitively waits on through the user-data template) to reach `running` state. If the policy were not yet attached, the CLI call fails, stdout is empty, `COUNT != masters_count`, and it simply retries. There is no hard failure mode.

3. **Timing in a real apply:** the policy attach (`PutRolePolicy`) is a sub-second call unlocked at the same moment as the profile creation (right after the role), while the instance's launch sits behind profile → launch config → ASG → `RunInstances` → OS boot (~tens of seconds). The policy is attached long before the first `describe-instances` call executes, and even a delayed attach would only add a few retries, not an incorrect result.

**Conclusion:** The two resources are genuinely related (the instance uses the role; its bootstrap script needs the `ec2:DescribeInstances` permission the policy grants), and the edge is unexpressed. But there is no *concrete* ordering requirement: the instance does not need the policy at creation time, and its bootstrap is a poll-until-success loop that cannot be broken by — and in practice never even observes — a late-attached policy. Both run1 and run2 identify the same non-required ordering.

Incorrect