#include <stdio.h>
#include <string.h>

#include "handlers.h"

/* CHECK, not assert() — a Release build (-DNDEBUG) compiles assert() away, which would make the tests
 * pass vacuously. This is explicit and NDEBUG-independent. */
#define CHECK(cond, msg)                    \
  do {                                      \
    if (!(cond)) {                          \
      fprintf(stderr, "FAIL: %s\n", (msg)); \
      return 1;                             \
    }                                       \
  } while (0)

int main(int argc, char **argv) {
  if (argc > 1 && strcmp(argv[1], "--selfcheck") == 0) {
    /* Deliberate failure — proves the lane propagates. Fail-closed: if this branch is removed,
     * --selfcheck falls through to the passing checks below (exit 0) → the guard reports LANE BROKEN. */
    CHECK(0, "selfcheck: the golden-path c lane must surface this failure (exit non-zero)");
  }
  CHECK(strstr(golden_health_json(), "ok") != NULL, "health");
  CHECK(strstr(golden_ready_json(), "ready") != NULL, "ready");
  CHECK(strstr(golden_hello_json(), "hello, weyland") != NULL, "hello message");
  CHECK(strstr(golden_hello_json(), "golden-c-libmicrohttpd") != NULL, "hello service");
  CHECK(strstr(golden_metrics_text(), "golden_hello_requests") != NULL, "metrics");
  printf("OK: 5 checks passed\n");
  return 0;
}
