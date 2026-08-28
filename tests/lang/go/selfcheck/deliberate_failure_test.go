//go:build deliberate

// Run ONLY by `run-lang-tests.sh go --self-check` (which passes -tags deliberate).
// The build tag is what keeps a plain `go test ./...` from ever seeing this file, so the fixture
// can pass normally while still proving the lane can fail.
package selfcheck

import "testing"

func TestDeliberateFailure(t *testing.T) {
	t.Fatal("deliberate: this failure is the point")
}
