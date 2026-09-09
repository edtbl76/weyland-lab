# frozen_string_literal: true

require_relative "test_helper"

# Golden-path contract tests — drive the REAL Sinatra app in-process via rack-test (no server).
class ContractTest < Minitest::Test
  include Rack::Test::Methods

  def app
    GoldenApp
  end

  def test_health_is_ok
    get "/health"
    assert last_response.ok?
    assert_includes last_response.body, "ok"
  end

  def test_ready_is_ready
    get "/ready"
    assert last_response.ok?
    assert_includes last_response.body, "ready"
  end

  def test_hello_returns_known_payload
    get "/hello"
    assert last_response.ok?
    assert_includes last_response.body, "hello, weyland"
    assert_includes last_response.body, "golden-ruby-sinatra"
  end

  def test_metrics_exposes_prometheus
    get "/metrics"
    assert last_response.ok?
    assert_includes last_response.body, "golden_hello_requests"
  end
end
