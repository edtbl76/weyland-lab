defmodule GoldenPlug.Application do
  @moduledoc false
  use Application

  @impl true
  def start(_type, _args) do
    port = String.to_integer(System.get_env("PORT", "8080"))

    children = [
      {Bandit, plug: GoldenPlug.Router, scheme: :http, port: port}
    ]

    Supervisor.start_link(children, strategy: :one_for_one, name: GoldenPlug.Supervisor)
  end
end
