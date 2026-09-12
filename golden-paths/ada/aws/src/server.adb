--  Golden path — Ada / AWS (Ada Web Server), built via Alire (B164 optional-language wave).
--  Runnable, ephemeral, extendable. Conforms to the golden-path contract
--  (docs/design/golden-paths.md): GET /health /ready /metrics /hello. Binds 0.0.0.0:8080 (AWS's
--  default host "" is all interfaces). Scaffold FROM it: scripts/new-service.sh ada/aws <your-service>.
with Ada.Text_IO;

with AWS.Messages;
with AWS.Response;
with AWS.Server;
with AWS.Status;

with Golden_Handlers;

procedure Server is

   Port : constant := 8080;

   --  The contract router. Dispatches on the request URI; the payloads come from Golden_Handlers,
   --  the same pure builders the AUnit suite asserts on.
   function Router (Request : AWS.Status.Data) return AWS.Response.Data is
      URI : constant String := AWS.Status.URI (Request);
   begin
      if URI = "/health" then
         return AWS.Response.Build ("application/json", Golden_Handlers.Health_JSON);
      elsif URI = "/ready" then
         return AWS.Response.Build ("application/json", Golden_Handlers.Ready_JSON);
      elsif URI = "/hello" then
         return AWS.Response.Build ("application/json", Golden_Handlers.Hello_JSON);
      elsif URI = "/metrics" then
         return AWS.Response.Build ("text/plain; version=0.0.4", Golden_Handlers.Metrics_Text);
      else
         return AWS.Response.Build
           ("text/plain", "not found", Status_Code => AWS.Messages.S404);
      end if;
   end Router;

   Web_Server : AWS.Server.HTTP;

begin
   --  Structured startup log line (the observability facet's logging half; /metrics is the other).
   Ada.Text_IO.Put_Line
     ("{""service"":""" & Golden_Handlers.Service_Name & """,""msg"":""listening on :8080""}");

   --  Router is nested, so 'Unrestricted_Access is required to satisfy AWS.Response.Callback's
   --  library-level accessibility (a standard AWS idiom).
   AWS.Server.Start
     (Web_Server,
      Name     => Golden_Handlers.Service_Name,
      Callback => Router'Unrestricted_Access,
      Port     => Port);

   AWS.Server.Wait (AWS.Server.Forever);  --  run until the container is torn down
end Server;
