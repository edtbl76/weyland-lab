--  AUnit harness. A normal run executes the 4 contract tests and exits 0. `test_runner --selfcheck`
--  flips Test_Config.Selfcheck BEFORE the suite is built, which registers the deliberate failure, so
--  the run exits non-zero — proving the runner propagates failure. The exit status comes from
--  Test_Runner_With_Status (not just a printed report), so a CI gate can read $? directly.
with Ada.Command_Line; use Ada.Command_Line;

with AUnit;
with AUnit.Reporter.Text;
with AUnit.Run;

with Golden_Suite;
with Test_Config;

procedure Test_Runner is
   use type AUnit.Status;
   function Run is new AUnit.Run.Test_Runner_With_Status (Golden_Suite);
   Reporter : AUnit.Reporter.Text.Text_Reporter;
begin
   for I in 1 .. Argument_Count loop
      if Argument (I) = "--selfcheck" then
         Test_Config.Selfcheck := True;
      end if;
   end loop;

   if Run (Reporter) = AUnit.Success then
      Set_Exit_Status (Success);
   else
      Set_Exit_Status (Failure);
   end if;
end Test_Runner;
