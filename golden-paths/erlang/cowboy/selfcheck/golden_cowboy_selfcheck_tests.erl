%% Deliberately-failing test — proves the erlang/cowboy lane PROPAGATES failure (exit non-zero).
%%
%% It lives in selfcheck/, which is compiled ONLY under the `selfcheck` rebar3 profile (rebar.config).
%% A normal `rebar3 eunit` never sees this module and passes; `rebar3 as selfcheck eunit` compiles it and
%% the run exits non-zero. This mirrors the go exemplar's `deliberate` build tag.
-module(golden_cowboy_selfcheck_tests).

-include_lib("eunit/include/eunit.hrl").

deliberate_failure_test() ->
    ?assertEqual(
        ok,
        {selfcheck, "the golden-path erlang/cowboy lane must surface this failure (exit non-zero)"}
    ).
