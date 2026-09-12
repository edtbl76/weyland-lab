# Golden path — R / plumber (B164 optional wave).
#
# Pure, framework-free payload builders + Prometheus renderer. Sourced by BOTH plumber.R
# (the live service) and the testthat suite (headless). Kept free of any plumber/httpuv
# dependency so the contract tests exercise the exact payload shapes without binding a
# server in-process — the C/C++ golden-path pattern (docs/design/golden-paths.md): the
# pure payload-builders are unit-tested; the real server is proven by the curl smoke.

SERVICE_NAME <- "golden-r-plumber"

# --- pure payload builders (unit-tested headless) ---

health_payload <- function() list(status = "ok")

ready_payload <- function() list(status = "ready")

hello_payload <- function() list(service = SERVICE_NAME, message = "hello, weyland")

# Encode a payload exactly as the live endpoints do (scalars unboxed), so a test asserting
# on this string is asserting on the bytes a client actually receives.
payload_json <- function(x) {
  as.character(jsonlite::toJSON(x, auto_unbox = TRUE))
}

# Render a minimal-but-valid Prometheus text exposition (format version 0.0.4).
render_metrics <- function(hits) {
  paste0(
    "# HELP golden_hello_requests_total Calls to the demo /hello endpoint\n",
    "# TYPE golden_hello_requests_total counter\n",
    "golden_hello_requests_total ", hits, "\n"
  )
}
