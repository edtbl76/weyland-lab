package fixture

import "testing"

// TestHello proves the Go lane runs: toolchain, module resolution, race detector, coverage.
func TestHello(t *testing.T) {
	if got := Hello(); got != "hello, weyland" {
		t.Fatalf("Hello() = %q, want %q", got, "hello, weyland")
	}
}
