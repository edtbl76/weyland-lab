# Golden-path self-test (R/plumber) — the lane probe + contract proof.
#
# Exercises the PURE payload builders headless (the C/C++ golden-path pattern): plumber binds
# httpuv to a real socket, so rather than stand the server up in-process we assert on the exact
# payload shapes/bytes the live endpoints emit. The running image is proven separately by the
# curl smoke (smoke.sh / .smoke). Run: Rscript -e 'testthat::test_dir("tests")'.
library(testthat)

# Locate payloads.R whether test_dir runs us with wd = tests/ or wd = the golden-path root.
if (!exists("hello_payload")) {
  hit <- Find(file.exists, c(
    file.path("..", "payloads.R"),
    "payloads.R",
    file.path("golden-paths", "r", "plumber", "payloads.R")
  ))
  if (is.null(hit)) stop("test-contract.R: cannot locate payloads.R")
  source(hit)
}

test_that("/health builder returns status ok", {
  expect_equal(health_payload(), list(status = "ok"))
})

test_that("/ready builder returns status ready", {
  expect_equal(ready_payload(), list(status = "ready"))
})

test_that("/hello builder returns the known payload", {
  expect_equal(hello_payload(), list(service = "golden-r-plumber", message = "hello, weyland"))
})

test_that("/hello serializes to the exact known JSON bytes (scalars unboxed)", {
  expect_equal(
    payload_json(hello_payload()),
    '{"service":"golden-r-plumber","message":"hello, weyland"}'
  )
})

test_that("/metrics renders a minimal-but-valid Prometheus exposition", {
  txt <- render_metrics(3L)
  expect_match(txt, "# HELP golden_hello_requests_total", fixed = TRUE)
  expect_match(txt, "# TYPE golden_hello_requests_total counter", fixed = TRUE)
  expect_match(txt, "golden_hello_requests_total 3", fixed = TRUE)
})
