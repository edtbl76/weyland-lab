with AUnit.Assertions; use AUnit.Assertions;

package body Selfcheck_Tests is

   procedure Test_Deliberate_Failure (T : in out AUnit.Test_Cases.Test_Case'Class) is
      pragma Unreferenced (T);
   begin
      Assert (False,
              "selfcheck: the golden-path ada lane must surface this failure (exit non-zero)");
   end Test_Deliberate_Failure;

   overriding procedure Register_Tests (T : in out Test) is
      use AUnit.Test_Cases.Registration;
   begin
      Register_Routine (T, Test_Deliberate_Failure'Access, "deliberate failure");
   end Register_Tests;

   overriding function Name (T : Test) return AUnit.Message_String is
      pragma Unreferenced (T);
   begin
      return AUnit.Format ("Golden Ada/AWS selfcheck (deliberate failure)");
   end Name;

end Selfcheck_Tests;
