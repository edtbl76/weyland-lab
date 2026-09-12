--  A tiny mutable flag the test runner sets from its command line BEFORE the suite is built, and that
--  Golden_Suite reads to decide whether to register the deliberately-failing selfcheck test. This is
--  the seam that keeps the selfcheck out of a normal run yet lets `--selfcheck` force it to execute.
package Test_Config is
   Selfcheck : Boolean := False;
end Test_Config;
