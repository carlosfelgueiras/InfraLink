The project ID comes from `google_project`, not from the services resource, so nothing links the channels to the API activation. The channels resource has no `depends_on`. The Monitoring API has to be enabled before channels can be created, and a user can enable it through `var.services`. The report is correct.

Correct