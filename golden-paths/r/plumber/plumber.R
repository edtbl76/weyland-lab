# Golden path — R / plumber (B164 optional wave).
#
# The idiomatic plumber baseline. Runnable, ephemeral, extendable. Conforms to the golden-path
# contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
# Scaffold FROM it: scripts/new-service.sh r/plumber <your-service>.
#
# Endpoint bodies delegate to the pure builders in payloads.R so the payload shapes are
# unit-testable headless (the C/C++ golden-path pattern) while this file wires them onto the
# HTTP surface. entrypoint.R plumbs this file and binds 0.0.0.0:8080. Run from this directory
# (the container WORKDIR is /app, where both files live).

library(plumber)

if (!exists("hello_payload")) {
  hit <- Find(file.exists, c("payloads.R", file.path("golden-paths", "r", "plumber", "payloads.R")))
  if (is.null(hit)) stop("plumber.R: cannot locate payloads.R (run from the golden-path directory)")
  source(hit)
}

# In-memory hello counter; an environment so the closures mutate one shared slot.
.state <- new.env(parent = emptyenv())
.state$hello_hits <- 0L

#* @get /health
#* @serializer unboxedJSON
function() health_payload()

#* @get /ready
#* @serializer unboxedJSON
function() ready_payload()

#* @get /hello
#* @serializer unboxedJSON
function() {
  .state$hello_hits <- .state$hello_hits + 1L
  hello_payload()
}

#* @get /metrics
#* @serializer text
function(res) {
  res$setHeader("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
  render_metrics(.state$hello_hits)
}
