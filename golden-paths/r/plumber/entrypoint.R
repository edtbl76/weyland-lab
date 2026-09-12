# Golden path — R / plumber (B164). Plumbs plumber.R and binds 0.0.0.0:8080.
library(plumber)

# Structured startup log line (matches the estate's JSON-on-startup convention).
source("payloads.R")
cat(sprintf('{"service":"%s","msg":"listening on :8080"}\n', SERVICE_NAME))

pr("plumber.R") |>
  pr_run(host = "0.0.0.0", port = 8080)
