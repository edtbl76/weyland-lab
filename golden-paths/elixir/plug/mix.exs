defmodule GoldenPlug.MixProject do
  use Mix.Project

  # Golden path — Elixir / Plug (B160). The lean sibling of the Phoenix flagship: Plug.Router on
  # Bandit, no framework ceremony. Contract: /health /ready /metrics /hello.
  def project do
    [
      app: :golden_plug,
      version: "0.1.0",
      elixir: "~> 1.17",
      start_permanent: Mix.env() == :prod,
      deps: deps()
    ]
  end

  def application do
    [
      extra_applications: [:logger],
      mod: {GoldenPlug.Application, []}
    ]
  end

  defp deps do
    [
      {:plug, "~> 1.16"},
      {:bandit, "~> 1.5"},
      {:jason, "~> 1.4"},
      {:credo, "~> 1.7", only: [:dev, :test], runtime: false}
    ]
  end
end
