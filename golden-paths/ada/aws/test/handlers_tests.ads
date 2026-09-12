with AUnit;
with AUnit.Test_Cases;

--  Contract tests over the pure payload builders (Golden_Handlers). The real AWS server is proven
--  end-to-end by the .smoke curl; these assert the payloads the router hands back.
package Handlers_Tests is

   type Test is new AUnit.Test_Cases.Test_Case with null record;

   overriding procedure Register_Tests (T : in out Test);
   overriding function Name (T : Test) return AUnit.Message_String;

end Handlers_Tests;
