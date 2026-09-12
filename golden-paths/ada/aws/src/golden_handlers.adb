package body Golden_Handlers is

   function Health_JSON return String is
     ("{""status"":""ok""}");

   function Ready_JSON return String is
     ("{""status"":""ready""}");

   function Hello_JSON return String is
     ("{""service"":""golden-ada-aws"",""message"":""hello, weyland""}");

   --  Prometheus text exposition. LF-terminated lines, one HELP/TYPE/sample triple — minimal valid.
   function Metrics_Text return String is
     ("# HELP golden_hello_requests_total Calls to /hello" & ASCII.LF
      & "# TYPE golden_hello_requests_total counter" & ASCII.LF
      & "golden_hello_requests_total 0" & ASCII.LF);

end Golden_Handlers;
