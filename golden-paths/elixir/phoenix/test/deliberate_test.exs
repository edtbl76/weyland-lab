defmodule GoldenPhoenix.DeliberateTest do
  # Deliberately-failing test — proves the elixir lane PROPAGATES failure. It carries @tag :selfcheck;
  # test_helper excludes that tag from a normal run and the lane self-check runs ONLY it via
  # `mix test --only selfcheck`. Tag-based (not a name filter) → fail-closed on a rename.
  use ExUnit.Case

  @tag :selfcheck
  test "deliberate failure" do
    flunk("selfcheck: the golden-path elixir lane must surface this failure (exit non-zero)")
  end
end
