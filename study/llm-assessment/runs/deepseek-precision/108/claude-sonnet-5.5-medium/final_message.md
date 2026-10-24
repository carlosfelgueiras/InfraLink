Neither policy is in the integration's dependencies. The integration depends only on the role (through the time_sleep and the role ARN). The Splunk provider docs say role policies must be in depends_on. With use_metric_streams_sync, the integration creation validates the role's permissions, including the metric-stream actions. The missing ordering is real.

Correct