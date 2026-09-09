#include <doctest/doctest.h>

#include <string>

#include "handlers.hpp"

TEST_CASE("health is ok") {
  CHECK(golden::health_json().find("ok") != std::string::npos);
}

TEST_CASE("ready is ready") {
  CHECK(golden::ready_json().find("ready") != std::string::npos);
}

TEST_CASE("hello returns the known payload") {
  const auto body = golden::hello_json();
  CHECK(body.find("hello, weyland") != std::string::npos);
  CHECK(body.find("golden-cpp-httplib") != std::string::npos);
}

TEST_CASE("metrics exposes prometheus") {
  CHECK(golden::metrics_text().find("golden_hello_requests") != std::string::npos);
}
