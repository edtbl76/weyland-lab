# frozen_string_literal: true

require_relative "boot"

# Minimal Rails: the framework core + Action Controller only. No Active Record, no Action View,
# no Action Mailer — an API service needs none of them, and leaving them out keeps the boot fast
# and the image small. This is the honest `--api --minimal` shape, hand-authored so the whole
# golden path is legible in one directory.
require "rails"
require "action_controller/railtie"

module GoldenRails
  class Application < Rails::Application
    config.load_defaults 8.0

    # API-only: no cookies/sessions/flash middleware, no view layer.
    config.api_only = true

    # A golden path is exercised ephemerally, never as a long-lived deploy, so eager loading buys
    # nothing and reloading is irrelevant.
    config.eager_load = false

    # Log to stdout so the ephemeral smoke Job's logs are visible and no log/ directory is required.
    config.logger = ActiveSupport::Logger.new($stdout)
    config.log_level = :info

    # A real service reads this from encrypted credentials or an env var; a LAN-only canary that
    # signs nothing can carry a fixed non-secret so boot never demands credentials.
    config.secret_key_base = "golden-rails-lab-canary-not-a-secret"

    # Allow any Host header — the ephemeral Job curls 127.0.0.1 and a real service sets its own
    # allowlist. Clearing avoids Rails' host-authorization blocking the smoke.
    config.hosts.clear
  end
end
