%% Compiled Cowboy dispatch for the whole contract. Shared by the app (live listener) and the eunit
%% suite (a listener on an ephemeral port), so tests exercise the SAME routing the image serves.
-module(golden_cowboy_router).

-export([dispatch/0]).

dispatch() ->
    cowboy_router:compile([
        {'_', [
            {"/health",  golden_cowboy_handler, health},
            {"/ready",   golden_cowboy_handler, ready},
            {"/hello",   golden_cowboy_handler, hello},
            {"/metrics", golden_cowboy_handler, metrics}
        ]}
    ]).
