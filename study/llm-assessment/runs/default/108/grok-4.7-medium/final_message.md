The reported dependency is real and is not expressed in the configuration.

`signalfx_aws_integration.integration` sets `use_metric_streams_sync = true`. Enabling that flag makes Splunk Observability Cloud assume the integration role and call CloudWatch metric-stream APIs (`Get`/`List`/`Put`/`Delete`/`Start`/`StopMetricStream`) plus `iam:PassRole`. Those permissions live only on `aws_iam_role_policy.splunk_managed_policy`. The provider waits during create and delete until metric-stream sync reaches `ENABLED` or `DISABLED`, so the policy must exist before the integration is created and must still exist while it is destroyed. The provider docs say to list role-related resources, including the policy attachment, in `depends_on` for that cleanup order.

The integration only references `aws_iam_role.splunk_integration.arn` and `time_sleep.wait_30_seconds`, and that sleep waits only on the role. The metric-stream policy is a sibling of the sleep, not an ancestor of the integration, so Terraform can create the integration before the policy is attached and can delete the policy before metric-stream cancellation finishes.

Correct