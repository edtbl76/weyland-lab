# frozen_string_literal: true

ENV["RACK_ENV"] ||= "test"

require_relative "../app"
require "rack/test"
require "minitest/autorun"
