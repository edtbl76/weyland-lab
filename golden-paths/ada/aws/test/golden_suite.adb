with AUnit.Test_Suites; use AUnit.Test_Suites;

with Handlers_Tests;
with Selfcheck_Tests;
with Test_Config;

function Golden_Suite return Access_Test_Suite is
   Result : constant Access_Test_Suite := New_Suite;
begin
   Result.Add_Test (new Handlers_Tests.Test);
   if Test_Config.Selfcheck then
      Result.Add_Test (new Selfcheck_Tests.Test);
   end if;
   return Result;
end Golden_Suite;
