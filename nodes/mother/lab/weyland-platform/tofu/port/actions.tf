# Port self-service actions (B58 IaC, Port lane). The "easy button" for the data mesh: wake/sleep the
# rarely-used data-mesh stores on demand to free/reclaim RAM during the day. Routes through the
# self-hosted port-agent (agent = true, LAN-only) → store-scaler service → deployments/scale.
# See docs/schedules.md, k8s/port-agent/, services/store-scaler/.
#
# NOTE: written against provider port-labs/port-labs ~> 2.0. Run `tofu plan` before apply — if the
# provider objects to a field here, adjust; plan is a safe dry-run gate (nothing applied until you say so).
resource "port_action" "scale_data_mesh_store" {
  identifier  = "scale_data_mesh_store"
  title       = "Scale data-mesh store"
  icon        = "Cluster"
  description = "Wake or sleep a rarely-used data-mesh store (Cockroach/Mongo/MySQL/GizmoSQL) to free or reclaim RAM."

  self_service_trigger = {
    operation = "CREATE"
    user_properties = {
      string_props = {
        store = {
          title    = "Store"
          required = true
          enum     = ["cockroachdb", "mongodb", "mysql", "gizmosql"]
        }
        action = {
          title    = "Action"
          required = true
          enum     = ["wake", "sleep"]
          default  = "wake"
        }
      }
    }
  }

  # agent = true → Port pushes the run to Kafka for the self-hosted port-agent instead of calling the URL
  # directly (which the LAN would block). The agent's controlThePayloadConfig sets the real request.
  webhook_method = {
    url    = "http://store-scaler.data-mesh.svc.cluster.local/scale"
    method = "POST"
    agent  = true
  }
}
