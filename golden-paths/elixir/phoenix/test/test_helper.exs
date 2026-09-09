# The deliberately-failing test carries @tag :selfcheck; a normal `mix test` excludes it here and the
# lane self-check runs ONLY it via `mix test --only selfcheck`. Tag-based → fail-closed on a rename.
ExUnit.start(exclude: [:selfcheck])
