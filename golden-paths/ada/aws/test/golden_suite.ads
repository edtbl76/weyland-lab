with AUnit.Test_Suites;

--  Builds the contract suite. Registers the deliberately-failing Selfcheck_Tests ONLY when
--  Test_Config.Selfcheck is set. Fail-closed: if that guard were removed, --selfcheck would run just
--  the passing contract tests (exit 0) and the lane self-check would report LANE BROKEN rather than
--  silently pass — the same fail-open trap the C/Elixir golden paths guard against.
function Golden_Suite return AUnit.Test_Suites.Access_Test_Suite;
