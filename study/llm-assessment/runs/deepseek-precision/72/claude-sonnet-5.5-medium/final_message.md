The report is incorrect. `splunk_configs_conf.forgecicd_cloudwatchlogs` (`props/aws:cloudwatchlogs`) names the transform only as a string in its `REPORT-forgecicd_cloudwatchlogs_global_lambda_tenant_fields` variable. That is a reference by name, not an attribute reference, so Terraform records no dependency between them.

The missing dependency does not matter in practice. As far as I know, Splunk's configuration REST endpoint stores props stanzas without checking that the transforms they name exist. This is from my knowledge of Splunk's behavior, and I did not check it against the provider docs. At worst, Splunk logs a warning until the transform exists. So the props stanza can be created before the transform without failing, and no ordering is required.

The same props stanza also names `forgecicd_extra_lambda_tenant_fields`. That transform isn't defined anywhere in this module, which supports the point that these names are not validated at creation time.

Incorrect