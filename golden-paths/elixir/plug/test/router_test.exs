defmodule GoldenPlug.RouterTest do
  use ExUnit.Case, async: true
  import Plug.Test

  @opts GoldenPlug.Router.init([])

  defp call(path) do
    conn(:get, path) |> GoldenPlug.Router.call(@opts)
  end

  test "health is ok" do
    conn = call("/health")
    assert conn.status == 200
    assert conn.resp_body =~ "ok"
  end

  test "ready is ready" do
    conn = call("/ready")
    assert conn.status == 200
    assert conn.resp_body =~ "ready"
  end

  test "hello returns the known payload" do
    conn = call("/hello")
    assert conn.status == 200
    assert conn.resp_body =~ "hello, weyland"
    assert conn.resp_body =~ "golden-elixir-plug"
  end

  test "metrics exposes prometheus" do
    conn = call("/metrics")
    assert conn.status == 200
    assert conn.resp_body =~ "golden_hello_requests"
  end
end
