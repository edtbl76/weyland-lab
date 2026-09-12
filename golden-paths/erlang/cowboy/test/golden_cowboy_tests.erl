%% Golden-path self-test (Erlang/Cowboy) — the lane probe + contract proof.
%%
%% Starts a real Cowboy listener on an ephemeral port and drives the four endpoints over HTTP with
%% inets/httpc — exercising the actual routing the image serves, not a mock.
-module(golden_cowboy_tests).

-include_lib("eunit/include/eunit.hrl").

contract_test_() ->
    {setup, fun setup/0, fun cleanup/1, fun tests/1}.

setup() ->
    {ok, _} = application:ensure_all_started(cowboy),
    {ok, _} = application:ensure_all_started(inets),
    Dispatch = golden_cowboy_router:dispatch(),
    {ok, _} = cowboy:start_clear(test_http, [{port, 0}], #{env => #{dispatch => Dispatch}}),
    ranch:get_port(test_http).

cleanup(_Port) ->
    ok = cowboy:stop_listener(test_http).

tests(Port) ->
    [
        {"GET /health is 200 + status ok",
            ?_test(assert_needle(Port, "/health", <<"\"status\":\"ok\"">>))},
        {"GET /ready is 200 + status ready",
            ?_test(assert_needle(Port, "/ready", <<"\"status\":\"ready\"">>))},
        {"GET /hello returns the known payload", ?_test(assert_hello(Port))},
        {"GET /metrics exposes the prometheus counter", ?_test(assert_metrics(Port))}
    ].

assert_needle(Port, Path, Needle) ->
    {Status, Body} = do_get(Port, Path),
    ?assertEqual(200, Status),
    ?assert(binary:match(Body, Needle) =/= nomatch).

assert_hello(Port) ->
    {Status, Body} = do_get(Port, "/hello"),
    ?assertEqual(200, Status),
    ?assert(binary:match(Body, <<"\"service\":\"golden-erlang-cowboy\"">>) =/= nomatch),
    ?assert(binary:match(Body, <<"\"message\":\"hello, weyland\"">>) =/= nomatch).

assert_metrics(Port) ->
    %% Hit /hello first so the counter has moved, then assert the exposition names the metric.
    {200, _} = do_get(Port, "/hello"),
    {Status, Body} = do_get(Port, "/metrics"),
    ?assertEqual(200, Status),
    ?assert(binary:match(Body, <<"golden_hello_requests_total">>) =/= nomatch).

do_get(Port, Path) ->
    Url = "http://127.0.0.1:" ++ integer_to_list(Port) ++ Path,
    {ok, {{_, Status, _}, _Headers, Body}} =
        httpc:request(get, {Url, []}, [], [{body_format, binary}]),
    {Status, Body}.
