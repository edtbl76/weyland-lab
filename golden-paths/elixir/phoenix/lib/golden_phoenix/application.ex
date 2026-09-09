defmodule GoldenPhoenix.Application do
  # See https://elixir.hexdocs.pm/Application.html
  # for more information on OTP Applications
  @moduledoc false

  use Application

  @impl true
  def start(_type, _args) do
    children = [
      GoldenPhoenixWeb.Telemetry,
      {DNSCluster, query: Application.get_env(:golden_phoenix, :dns_cluster_query) || :ignore},
      {Phoenix.PubSub, name: GoldenPhoenix.PubSub},
      # Start a worker by calling: GoldenPhoenix.Worker.start_link(arg)
      # {GoldenPhoenix.Worker, arg},
      # Start to serve requests, typically the last entry
      GoldenPhoenixWeb.Endpoint
    ]

    # See https://elixir.hexdocs.pm/Supervisor.html
    # for other strategies and supported options
    opts = [strategy: :one_for_one, name: GoldenPhoenix.Supervisor]
    Supervisor.start_link(children, opts)
  end

  # Tell Phoenix to update the endpoint configuration
  # whenever the application is updated.
  @impl true
  def config_change(changed, _new, removed) do
    GoldenPhoenixWeb.Endpoint.config_change(changed, removed)
    :ok
  end
end
