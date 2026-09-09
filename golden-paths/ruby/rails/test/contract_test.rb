# frozen_string_literal: true

require_relative "test_helper"

# Golden-path contract tests — drive the REAL app through the full Rails stack (router + controllers).
class ContractTest < ActionDispatch::IntegrationTest
  test "health is ok" do
    get "/health"
    assert_response :success
    assert_match "ok", response.body
  end

  test "ready is ready" do
    get "/ready"
    assert_response :success
    assert_match "ready", response.body
  end

  test "hello returns the known payload" do
    get "/hello"
    assert_response :success
    assert_match "hello, weyland", response.body
    assert_match "golden-ruby-rails", response.body
  end

  test "metrics exposes prometheus" do
    get "/metrics"
    assert_response :success
    assert_match "golden_hello_requests", response.body
  end
end
