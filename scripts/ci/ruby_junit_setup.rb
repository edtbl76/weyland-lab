# B189 phase 2b: turns on a JUnit report for the ruby lane WITHOUT touching a project's test helpers.
# run-lang-tests.sh loads it with RUBYOPT=-r<this file>, under a CI-only Gemfile that adds minitest-reporters
# (owner-approved 1.8.0) on top of the project's own, locked gems. The default reporter keeps the console output;
# the JUnit one writes TEST-<Class>.xml into WEYLAND_JUNIT_DIR (it must be set: a missing dir is an error, never
# a silently unreported run). Observed 2026-11-07 in ruby:3.3: works under the Rails test task and plain rake;
# a failing test still exits 1; Trunk's parser counts the reports.
#
# bundler/setup FIRST. RUBYOPT -r runs before `bundle exec` activates the locked gems, so a bare require picked the
# newest minitest on the machine: in the lane the Rails fixture had installed minitest 6.0.6, and Sinatra (locked to
# 5.27.0) then died with "You have already activated minitest 6.0.6, but your Gemfile requires minitest 5.27.0"
# (found 2026-11-07; a hand-run passed only because Sinatra went first in a fresh container).
require "bundler/setup"
require "minitest/reporters"
Minitest::Reporters.use!(
  [Minitest::Reporters::DefaultReporter.new,
   Minitest::Reporters::JUnitReporter.new(ENV.fetch("WEYLAND_JUNIT_DIR"), false)]
)
