%% Root supervisor. The Cowboy listener lives under ranch's own supervisor (started by cowboy:start_clear),
%% so this one carries no children — it exists to satisfy the OTP application `mod` contract.
-module(golden_cowboy_sup).
-behaviour(supervisor).

-export([start_link/0, init/1]).

start_link() ->
    supervisor:start_link({local, ?MODULE}, ?MODULE, []).

init([]) ->
    {ok, {#{strategy => one_for_one, intensity => 1, period => 5}, []}}.
