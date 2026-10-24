The report is incorrect.

`splunk_configs_conf.forgecicd_cloudwatchlogs` is declared in `props_cloudwatchlogs.tf`. It refers to the transform `forgecicd_cloudwatchlogs_lambda_tenant_fields` only through the plain string in its `REPORT-forgecicd_cloudwatchlogs_lambda_tenant_fields` variable. Terraform therefore infers no dependency between the two resources, as the reports say.

That missing link doesn't matter in practice, because the Splunk API doesn't require the transform to exist first. `splunk_configs_conf` writes each stanza through the configs REST endpoint as a plain set of key/value pairs. Splunk does not check that a `REPORT-*` value names an existing `transforms.conf` stanza when the props stanza is written. It resolves that name later, when the conf files are loaded and applied at index or search time. If the transform is missing at that point, Splunk skips it and logs a warning, and it picks the transform up as soon as it exists.

Creating the props stanza before the transform therefore doesn't fail or leave the props stanza broken. Ordering the two resources would only remove a short window of warnings.

Incorrect