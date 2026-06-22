# Brownfield import blocks — codify the remaining Port blueprints via `tofu plan -generate-config-out`.
# (cost already imported → its block removed.) After these import + a clean plan, DELETE this file — import
# blocks are one-shot; the resource .tf files are the durable config. NOTE: this imports the blueprint SCHEMAS
# only, not their entities (entities stay as data — onboard later if wanted).
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
