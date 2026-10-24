I now have all the evidence I need. Let me consolidate the dependency-graph analysis and the vendor documentation findings.

## Configuration facts (module `splunk_o11y_aws_integration_common`)

**`signalfx_aws_integration.integration`** (`signalfx.tf:5-18`) has these dependencies:
- `signalfx_aws_external_integration.integration` (via `integration_id`, `external_id` attribute refs)
- `aws_iam_role.splunk_integration` (via `role_arn = aws_iam_role.splunk_integration.arn`)
- `time_sleep.wait_30_seconds` (via `depends_on`) — and `time_sleep` itself depends **only** on `aws_iam_role.splunk_integration` (`signalfx.tf:23-28`)

**`aws_iam_role_policy.splunk_managed_policy`** (`role.tf:167-172`, name `"SplunkManagedMetricStreams"`) attaches to `aws_iam_role.splunk_integration` and grants `cloudwatch:GetMetricStream/ListMetricStreams/PutMetricStream/DeleteMetricStream/StartMetricStreams/StopMetricStreams` plus `iam:PassRole` on `role/splunk-metric-streams*` (commented "Role to be created by Cloudformation stack").

Nothing in the integration block references the policy — neither an attribute reference nor a `depends_on` entry. In the Terraform graph, `aws_iam_role_policy.splunk_managed_policy` and `signalfx_aws_integration.integration` are **siblings** (both only downstream of the role), so Terraform is free to create the integration before, or in parallel with, the policy. The `time_sleep` chain only covers the role, not the policies.

## Real-world ordering requirement

The integration sets `use_metric_streams_sync = true` and `enable_check_large_volume = true`. With metric-streams sync enabled, Splunk Observability Cloud assumes this role and creates/validates a CloudWatch metric stream (a CloudFormation stack creating the `splunk-metric-streams*` role) — which is precisely the set of permissions `splunk_managed_policy` grants. This is a concrete, not incidental, requirement:

- The official Splunk signalfx provider docs state: *"When AWS IAM role is also created by Terraform to enforce a proper cleanup sequence add role related resources as dependencies for the `signalfx_aws_integration` resource"*, and their example puts the role **and its policy attachment** in `depends_on` of `signalfx_aws_integration`.
- Cisco's troubleshooting doc (SPLK051128) confirms the failure mode: creating/enabling the integration fails when *"the policy is not applied to the role before Terraform tries to enable the integration"*, because AWS validates the assumed role's permissions during integration setup.
- It also matters for destroy ordering: the provider waits for metric-stream sync state transitions during deletion, and removing the policy (or role) first leads to `CANCELLATION_FAILED` / stuck integrations.

The module already goes partway (role → `time_sleep` → integration), acknowledging propagation ordering matters, but the metric-streams policy attachment is not ordered before the integration. Adding `aws_iam_role_policy.splunk_managed_policy` (no cycle: policy depends only on the role) is the vendor-documented pattern, and the diagnostic reports exactly this gap. Both run2 and run3 describe the same missing dependency, and their reasoning matches the resource semantics and provider documentation.

## Conclusion

The report is accurate: `signalfx_aws_integration.integration` requires `aws_iam_role_policy.splunk_managed_policy` to exist first (the metric-stream permissions must be attached to the role before Splunk validates/starts metric streams), and that ordering is currently absent from the configuration.

Correct