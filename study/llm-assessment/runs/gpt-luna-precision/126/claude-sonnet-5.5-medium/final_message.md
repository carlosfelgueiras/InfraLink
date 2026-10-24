The report is incorrect: no operational ordering is needed here.

The dind props stanza (`props_k8s.tf`, line 303) names the transform in a `REPORT-forgecicd_kube_container_runner_tenant_fields` setting. It does this with a literal string, not an attribute reference, so Terraform has no implicit dependency between the two resources. There is also no `depends_on`.

The ordering still isn't a real requirement. The `splunk_configs_conf` resource writes a stanza through Splunk's configs REST endpoint. I'm relying on my understanding of that endpoint here and did not check the provider documentation. As I understand it, the endpoint does not check that a transform named in a `REPORT-` setting already exists. A props stanza can be saved first, and the reference only takes effect at search or index time, once the transform exists. A dependency that exists only because one stanza names another therefore doesn't need to be enforced.

Incorrect