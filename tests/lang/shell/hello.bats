#!/usr/bin/env bats
# Hello-world fixture for the Shell lane (B88). Proves bats runs and the lane is wired.

@test "shell lane executes and can assert" {
  run printf 'hello, weyland'
  [ "$status" -eq 0 ]
  [ "$output" = "hello, weyland" ]
}
