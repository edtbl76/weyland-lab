with Ada.Strings.Fixed;

with AUnit.Assertions; use AUnit.Assertions;

with Golden_Handlers;

package body Handlers_Tests is

   function Contains (Haystack, Needle : String) return Boolean is
     (Ada.Strings.Fixed.Index (Haystack, Needle) > 0);

   procedure Test_Health (T : in out AUnit.Test_Cases.Test_Case'Class) is
      pragma Unreferenced (T);
   begin
      Assert (Contains (Golden_Handlers.Health_JSON, """status"":""ok"""),
              "health payload must report status ok");
   end Test_Health;

   procedure Test_Ready (T : in out AUnit.Test_Cases.Test_Case'Class) is
      pragma Unreferenced (T);
   begin
      Assert (Contains (Golden_Handlers.Ready_JSON, """status"":""ready"""),
              "ready payload must report status ready");
   end Test_Ready;

   procedure Test_Hello (T : in out AUnit.Test_Cases.Test_Case'Class) is
      pragma Unreferenced (T);
   begin
      Assert (Contains (Golden_Handlers.Hello_JSON, "hello, weyland"),
              "hello payload must carry the known message");
      Assert (Contains (Golden_Handlers.Hello_JSON, "golden-ada-aws"),
              "hello payload must carry the service name");
   end Test_Hello;

   procedure Test_Metrics (T : in out AUnit.Test_Cases.Test_Case'Class) is
      pragma Unreferenced (T);
   begin
      Assert (Contains (Golden_Handlers.Metrics_Text, "golden_hello_requests_total"),
              "metrics must expose the hello counter");
      Assert (Contains (Golden_Handlers.Metrics_Text, "# TYPE golden_hello_requests_total counter"),
              "metrics must be valid Prometheus text exposition");
   end Test_Metrics;

   overriding procedure Register_Tests (T : in out Test) is
      use AUnit.Test_Cases.Registration;
   begin
      Register_Routine (T, Test_Health'Access, "health payload");
      Register_Routine (T, Test_Ready'Access, "ready payload");
      Register_Routine (T, Test_Hello'Access, "hello payload");
      Register_Routine (T, Test_Metrics'Access, "metrics exposition");
   end Register_Tests;

   overriding function Name (T : Test) return AUnit.Message_String is
      pragma Unreferenced (T);
   begin
      return AUnit.Format ("Golden Ada/AWS contract payload builders");
   end Name;

end Handlers_Tests;
