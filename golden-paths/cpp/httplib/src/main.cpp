#include <httplib.h>

#include <cstdlib>

#include "handlers.hpp"

int main() {
  httplib::Server svr;

  svr.Get("/health", [](const httplib::Request&, httplib::Response& res) {
    res.set_content(golden::health_json(), "application/json");
  });
  svr.Get("/ready", [](const httplib::Request&, httplib::Response& res) {
    res.set_content(golden::ready_json(), "application/json");
  });
  svr.Get("/hello", [](const httplib::Request&, httplib::Response& res) {
    res.set_content(golden::hello_json(), "application/json");
  });
  svr.Get("/metrics", [](const httplib::Request&, httplib::Response& res) {
    res.set_content(golden::metrics_text(), "text/plain; version=0.0.4");
  });

  const char* port_env = std::getenv("PORT");
  const int port = port_env ? std::atoi(port_env) : 8080;
  svr.listen("0.0.0.0", port);
  return 0;
}
