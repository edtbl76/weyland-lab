defmodule GoldenPlug.Router do
  @moduledoc "Golden-path contract in one router: /health /ready /hello /metrics."
  use Plug.Router

  @service "golden-elixir-plug"

  plug(:match)
  plug(:dispatch)

  get "/health" do
    send_json(conn, %{status: "ok"})
  end

  get "/ready" do
    send_json(conn, %{status: "ready"})
  end

  get "/hello" do
    send_json(conn, %{service: @service, message: "hello, weyland"})
  end

  # Prometheus text exposition, hand-rolled to stay dependency-free.
  get "/metrics" do
    body =
      "# HELP golden_hello_requests_total Calls to /hello\n" <>
        "# TYPE golden_hello_requests_total counter\n" <>
        "golden_hello_requests_total 0\n"

    conn
    |> put_resp_content_type("text/plain; version=0.0.4")
    |> send_resp(200, body)
  end

  match _ do
    send_resp(conn, 404, "not found")
  end

  defp send_json(conn, data) do
    conn
    |> put_resp_content_type("application/json")
    |> send_resp(200, Jason.encode!(data))
  end
end
