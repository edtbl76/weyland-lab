# frozen_string_literal: true

# Deliberately-failing test — proves the ruby lane PROPAGATES failure. It lives in selfcheck/, which is
# OUTSIDE the `test` rake task's test/**/ glob, so a normal run never sees it; `rake test:selfcheck`
# runs ONLY it. Standalone (no Rails boot) so the self-check is fast and independent of the app.
require "minitest/autorun"

class DeliberateTest < Minitest::Test
  def test_deliberate_failure
    flunk "selfcheck: the golden-path ruby lane must surface this failure (exit non-zero)"
  end
end
