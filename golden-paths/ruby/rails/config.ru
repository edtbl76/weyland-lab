# frozen_string_literal: true

# Rack entrypoint — `puma config.ru` (and any Rack server) boots the app through here.
require_relative "config/environment"

run Rails.application
