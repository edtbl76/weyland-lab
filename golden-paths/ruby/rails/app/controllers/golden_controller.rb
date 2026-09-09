# frozen_string_literal: true

# The whole golden-path contract in one controller: /health /ready /hello /metrics.
class GoldenController < ApplicationController
  SERVICE_NAME = "golden-ruby-rails"

  def health
    render json: { status: "ok" }
  end

  def ready
    render json: { status: "ready" }
  end

  def hello
    render json: { service: SERVICE_NAME, message: "hello, weyland" }
  end

  # Prometheus text exposition, hand-rolled to stay dependency-free — a real service swaps in the
  # `prometheus-client` gem with a proper registry and process metrics.
  def metrics
    body = "# HELP golden_hello_requests_total Calls to /hello\n" \
           "# TYPE golden_hello_requests_total counter\n" \
           "golden_hello_requests_total 0\n"
    render plain: body, content_type: "text/plain; version=0.0.4"
  end
end
