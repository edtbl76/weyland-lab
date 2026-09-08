//go:build deliberate

// Deliberately-failing test behind the `deliberate` build tag — proves the go lane PROPAGATES failure.
// A normal `go test ./...` cannot see it; the lane self-check runs `go test -tags deliberate -run DeliberateFailure`.
package main

import "testing"

func TestDeliberateFailure(t *testing.T) {
	t.Fatal("selfcheck: the golden-path go lane must surface this failure (exit non-zero)")
}
