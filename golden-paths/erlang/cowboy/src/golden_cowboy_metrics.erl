%% Minimal Prometheus text exposition for the demo /hello counter. Backed by an OTP `counters` array
%% (atomic, lock-free) whose ref lives in persistent_term, so every request process shares one count.
-module(golden_cowboy_metrics).

-export([ensure/0, inc/0, value/0, render/0]).

-define(KEY, {?MODULE, hello_counter}).

%% Idempotent: create the counter once, reuse thereafter. Called at app start and lazily by the handlers
%% (so the eunit suite works whether or not the full OTP app was started).
ensure() ->
    case persistent_term:get(?KEY, undefined) of
        undefined ->
            Ref = counters:new(1, [write_concurrency]),
            persistent_term:put(?KEY, Ref),
            Ref;
        Ref ->
            Ref
    end.

inc() -> counters:add(ensure(), 1, 1).

value() -> counters:get(ensure(), 1).

-spec render() -> binary().
render() ->
    iolist_to_binary([
        <<"# HELP golden_hello_requests_total Calls to the demo /hello endpoint\n">>,
        <<"# TYPE golden_hello_requests_total counter\n">>,
        <<"golden_hello_requests_total ">>, integer_to_binary(value()), <<"\n">>
    ]).
