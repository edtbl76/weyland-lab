# frozen_string_literal: true

# Golden path — Ruby / Sinatra (B160). Modular style (a Sinatra::Base subclass) so tests can drive the
# app in-process via rack-test and config.ru can mount it — the same app object serves and is tested.
require "sinatra/base"
require "json"

class GoldenApp < Sinatra::Base
  SERVICE_NAME = "golden-ruby-sinatra"

  set :host_authorization, permitted_hosts: [] # LAN canary: accept any Host (the Job curls 127.0.0.1)

  get "/health" do
    content_type :json
    { status: "ok" }.to_json
  end

  get "/ready" do
    content_type :json
    { status: "ready" }.to_json
  end

  get "/hello" do
    content_type :json
    { service: SERVICE_NAME, message: "hello, weyland" }.to_json
  end

  # Prometheus text exposition, hand-rolled to stay dependency-free.
  get "/metrics" do
    content_type "text/plain; version=0.0.4"
    "# HELP golden_hello_requests_total Calls to /hello\n" \
      "# TYPE golden_hello_requests_total counter\n" \
      "golden_hello_requests_total 0\n"
  end
end
