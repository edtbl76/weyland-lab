# Brownfield import — generate ALL Port blueprints on a CLEAN slate (no resource .tf + empty state), which is the
# only state where the generator resolves the provider cleanly (import blocks for un-configured resources else
# resolve the provider by its TYPE name → phantom hashicorp/port-labs). Generate → clean → blueprints.tf → apply
# re-imports every one. Delete this file afterward.
import {
  to = port_blueprint.cost
  id = "cost"
}
import {
  to = port_blueprint.ci_pipeline
  id = "ci_pipeline"
}
import {
  to = port_blueprint.glitchtip_issue
  id = "glitchtip_issue"
}
import {
  to = port_blueprint.feature_flag
  id = "feature_flag"
}
import {
  to = port_blueprint.code_quality
  id = "code_quality"
}
import {
  to = port_blueprint.security_scan
  id = "security_scan"
}
import {
  to = port_blueprint.endpoint
  id = "endpoint"
}
