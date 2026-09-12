%% Pure payload builders — the known JSON bodies, independent of HTTP. Hand-rolled (flat string maps),
%% so the golden path pulls no JSON dependency beyond cowboy/cowlib/ranch.
-module(golden_cowboy_payload).

-export([service_name/0, health/0, ready/0, hello/0]).

-spec service_name() -> binary().
service_name() -> <<"golden-erlang-cowboy">>.

-spec health() -> binary().
health() -> <<"{\"status\":\"ok\"}">>.

-spec ready() -> binary().
ready() -> <<"{\"status\":\"ready\"}">>.

%% The SAME known payload shape the go exemplar serves: {"service":..., "message":"hello, weyland"}.
-spec hello() -> binary().
hello() ->
    iolist_to_binary([
        <<"{\"service\":\"">>, service_name(), <<"\",\"message\":\"hello, weyland\"}">>
    ]).
