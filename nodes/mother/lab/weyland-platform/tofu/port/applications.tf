# B82 — Port `component` catalog generated from the ONE canonical Application registry
# (services/weyland-dagster/weyland_pipeline/applications.yaml). Drift-proof: every component here comes from
# the same file datahub_emit.py reads, so Port + DataHub can't disagree. Design: aidlc-docs/application-taxonomy.md.
#
# Adds per component: is_data_application (bool) + datahub_application_url (link to the DataHub Application page,
# data-apps only). Pure-compute components get the flag = false and no link.
#
# Brownfield: the ~11 pre-existing Port components (created via MCP, NOT in tofu) must be reconciled before the
# first apply — see runbooks/opentofu.md § B82. Stale ones (hermes, the CT-102 ollama) get deleted; id-aligned
# survivors (weyland-tool-server, mlflow, n8n, open-webui) get `tofu import`ed into these addresses; id-mismatches
# (dagster→weyland-dagster, litellm-gateway→litellm) are recreated under the registry key.

locals {
  _app_registry  = yamldecode(file("${path.module}/../../services/weyland-dagster/weyland_pipeline/applications.yaml"))
  app_components = { for a in local._app_registry.applications : a.key => a }
  datahub_app_base = "https://datahub.weyland.lab/application"
}

resource "port_entity" "component" {
  for_each = local.app_components

  identifier = each.value.key
  title      = each.value.name
  blueprint  = "component"

  properties = {
    array_props   = null
    number_props  = null
    object_props  = null
    boolean_props = {
      is_data_application = each.value.datahub_application
    }
    string_props = merge(
      { description = each.value.description },
      each.value.datahub_application
        ? { datahub_application_url = "${local.datahub_app_base}/urn:li:application:${each.value.key}/Owned%20Assets" }
        : {}
    )
  }

  # relations intentionally UNMANAGED — the Port K8s exporter owns each component's k8sWorkload link;
  # Tofu managing relations here would flap against it every sync + wipe the B59 component→k8s_workload links.
  relations = null
}
