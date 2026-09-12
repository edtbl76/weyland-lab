--  Pure response-builders — the contract's payloads, factored out so they are unit-testable without the
--  HTTP layer (the C/C++ pattern: binding AWS in-process for a unit test is heavy, so AUnit tests these
--  pure functions and the smoke curls the real AWS server end-to-end). Golden-path contract
--  (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
package Golden_Handlers is

   Service_Name : constant String := "golden-ada-aws";

   function Health_JSON return String;
   --  {"status":"ok"}

   function Ready_JSON return String;
   --  {"status":"ready"}

   function Hello_JSON return String;
   --  {"service":"golden-ada-aws","message":"hello, weyland"}

   function Metrics_Text return String;
   --  Prometheus text exposition (minimal valid), hand-rolled to stay dependency-free.

end Golden_Handlers;
