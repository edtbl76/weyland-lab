%% Cowboy handler for the four contract endpoints. The route atom (health|ready|hello|metrics) is the
%% handler's init opts, wired in golden_cowboy_router.
-module(golden_cowboy_handler).
-behaviour(cowboy_handler).

-export([init/2]).

init(Req0, health) ->
    reply_json(Req0, golden_cowboy_payload:health(), health);
init(Req0, ready) ->
    reply_json(Req0, golden_cowboy_payload:ready(), ready);
init(Req0, hello) ->
    golden_cowboy_metrics:inc(),
    reply_json(Req0, golden_cowboy_payload:hello(), hello);
init(Req0, metrics) ->
    Req = cowboy_req:reply(200,
        #{<<"content-type">> => <<"text/plain; version=0.0.4; charset=utf-8">>},
        golden_cowboy_metrics:render(), Req0),
    {ok, Req, metrics}.

reply_json(Req0, Body, State) ->
    Req = cowboy_req:reply(200,
        #{<<"content-type">> => <<"application/json">>},
        Body, Req0),
    {ok, Req, State}.
