defmodule GoldenPhoenixWeb.GoldenController do
  @moduledoc "The whole golden-path contract in one controller: /health /ready /hello /metrics."
  use GoldenPhoenixWeb, :controller

  @service "golden-elixir-phoenix"

  def health(conn, _params), do: json(conn, %{status: "ok"})
  def ready(conn, _params), do: json(conn, %{status: "ready"})

  def hello(conn, _params) do
    json(conn, %{service: @service, message: "hello, weyland"})
  end

  # Prometheus text exposition, hand-rolled to stay dependency-free.
  def metrics(conn, _params) do
    body =
      "# HELP golden_hello_requests_total Calls to /hello\n" <>
        "# TYPE golden_hello_requests_total counter\n" <>
        "golden_hello_requests_total 0\n"

    conn
    |> put_resp_content_type("text/plain; version=0.0.4")
    |> send_resp(200, body)
  end
end
