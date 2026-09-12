%% Golden path — Erlang / Cowboy (B160-style).
%%
%% The idiomatic Cowboy baseline. Runnable, ephemeral, extendable. Conforms to the golden-path contract
%% (docs/design/golden-paths.md): GET /health /ready /metrics /hello on :8080. Scaffold FROM it:
%% scripts/new-service.sh erlang/cowboy <your-service>.
-module(golden_cowboy_app).
-behaviour(application).

-export([start/2, stop/1]).

start(_Type, _Args) ->
    %% Initialise the hello counter before the listener accepts traffic (avoids a first-request race).
    _ = golden_cowboy_metrics:ensure(),
    Port = port(),
    Dispatch = golden_cowboy_router:dispatch(),
    {ok, _} = cowboy:start_clear(golden_cowboy_http, [{port, Port}], #{env => #{dispatch => Dispatch}}),
    logger:info(#{service => <<"golden-erlang-cowboy">>, msg => <<"listening">>, port => Port}),
    golden_cowboy_sup:start_link().

stop(_State) ->
    _ = cowboy:stop_listener(golden_cowboy_http),
    ok.

%% Port from $PORT (the scaffold seam), default 8080 to match the golden-path contract.
port() ->
    case os:getenv("PORT") of
        false -> 8080;
        ""    -> 8080;
        P     -> list_to_integer(P)
    end.
