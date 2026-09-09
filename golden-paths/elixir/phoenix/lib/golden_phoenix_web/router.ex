defmodule GoldenPhoenixWeb.Router do
  use GoldenPhoenixWeb, :router

  pipeline :api do
    plug(:accepts, ["json"])
  end

  # The contract lives at the root (not /api): /health /ready /hello /metrics.
  scope "/", GoldenPhoenixWeb do
    pipe_through(:api)

    get("/health", GoldenController, :health)
    get("/ready", GoldenController, :ready)
    get("/hello", GoldenController, :hello)
    get("/metrics", GoldenController, :metrics)
  end
end
