#include "handlers.h"

const char *golden_service = "golden-c-libmicrohttpd";

const char *golden_health_json(void) { return "{\"status\":\"ok\"}"; }
const char *golden_ready_json(void) { return "{\"status\":\"ready\"}"; }

const char *golden_hello_json(void) {
  return "{\"service\":\"golden-c-libmicrohttpd\",\"message\":\"hello, weyland\"}";
}

/* Prometheus text exposition, hand-rolled to stay dependency-free. */
const char *golden_metrics_text(void) {
  return "# HELP golden_hello_requests_total Calls to /hello\n"
         "# TYPE golden_hello_requests_total counter\n"
         "golden_hello_requests_total 0\n";
}
