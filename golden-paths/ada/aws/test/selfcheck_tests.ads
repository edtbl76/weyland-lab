with AUnit;
with AUnit.Test_Cases;

--  Deliberately-failing test — proves the ada lane PROPAGATES failure. It is registered into the
--  suite ONLY when Test_Config.Selfcheck is set (i.e. test_runner was invoked with --selfcheck), so a
--  normal `test_runner` run never sees it and exits 0. Fail-closed: see Golden_Suite.
package Selfcheck_Tests is

   type Test is new AUnit.Test_Cases.Test_Case with null record;

   overriding procedure Register_Tests (T : in out Test);
   overriding function Name (T : Test) return AUnit.Message_String;

end Selfcheck_Tests;
