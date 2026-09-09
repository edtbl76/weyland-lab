# frozen_string_literal: true

Rails.application.routes.draw do
  get "/health",  to: "golden#health"
  get "/ready",   to: "golden#ready"
  get "/hello",   to: "golden#hello"
  get "/metrics", to: "golden#metrics"
end
