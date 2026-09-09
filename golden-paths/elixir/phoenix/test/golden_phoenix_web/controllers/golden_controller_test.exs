defmodule GoldenPhoenixWeb.GoldenControllerTest do
  use GoldenPhoenixWeb.ConnCase, async: true

  test "health is ok", %{conn: conn} do
    conn = get(conn, ~p"/health")
    assert response(conn, 200) =~ "ok"
  end

  test "ready is ready", %{conn: conn} do
    conn = get(conn, ~p"/ready")
    assert response(conn, 200) =~ "ready"
  end

  test "hello returns the known payload", %{conn: conn} do
    conn = get(conn, ~p"/hello")
    body = response(conn, 200)
    assert body =~ "hello, weyland"
    assert body =~ "golden-elixir-phoenix"
  end

  test "metrics exposes prometheus", %{conn: conn} do
    conn = get(conn, ~p"/metrics")
    assert response(conn, 200) =~ "golden_hello_requests"
  end
end
