# frozen_string_literal: true

# Rack entrypoint — `puma config.ru` (and any Rack server) mounts the modular app through here.
require_relative "app"

run GoldenApp
