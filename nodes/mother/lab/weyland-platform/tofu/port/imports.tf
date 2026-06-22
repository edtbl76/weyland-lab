# Brownfield import — ONE at a time (multi-import + non-default provider local name → phantom hashicorp/port-labs).
# Generate → clean → move to a real .tf → apply → swap the next blueprint in here. Delete this file when done.
import {
  to = port_blueprint.ci_pipeline
  id = "ci_pipeline"
}
