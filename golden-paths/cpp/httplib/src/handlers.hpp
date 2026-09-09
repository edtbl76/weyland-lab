#pragma once
// Pure response-builders — the contract's payloads, factored out so they are unit-testable without an
// HTTP layer (C++ has no in-process request mock like ring-mock/rack-test; the smoke curls the real
// server end-to-end, these tests cover the payload logic).
#include <string>

namespace golden {

inline const char* service() { return "golden-cpp-httplib"; }

inline std::string health_json() { return R"({"status":"ok"})"; }
inline std::string ready_json() { return R"({"status":"ready"})"; }

inline std::string hello_json() {
  return std::string(R"({"service":")") + service() + R"(","message":"hello, weyland"})";
}

// Prometheus text exposition, hand-rolled to stay dependency-free.
inline std::string metrics_text() {
  return "# HELP golden_hello_requests_total Calls to /hello\n"
         "# TYPE golden_hello_requests_total counter\n"
         "golden_hello_requests_total 0\n";
}

}  // namespace golden
