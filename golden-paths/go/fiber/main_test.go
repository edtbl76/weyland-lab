// Golden-path self-test (Go/Fiber) — the lane probe + contract proof, over app.Test().
package main

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func do(t *testing.T, path string) (int, map[string]string, string) {
	t.Helper()
	resp, err := Router().Test(httptest.NewRequest(http.MethodGet, path, nil))
	if err != nil {
		t.Fatalf("test %s: %v", path, err)
	}
	b, _ := io.ReadAll(resp.Body)
	var m map[string]string
	_ = json.Unmarshal(b, &m)
	return resp.StatusCode, m, string(b)
}

func TestHealthIsOK(t *testing.T) {
	code, body, _ := do(t, "/health")
	if code != http.StatusOK || body["status"] != "ok" {
		t.Fatalf("health: code=%d body=%v", code, body)
	}
}

func TestReadyIsReady(t *testing.T) {
	code, body, _ := do(t, "/ready")
	if code != http.StatusOK || body["status"] != "ready" {
		t.Fatalf("ready: code=%d body=%v", code, body)
	}
}

func TestHelloReturnsKnownPayload(t *testing.T) {
	code, body, _ := do(t, "/hello")
	if code != http.StatusOK || body["message"] != "hello, weyland" || body["service"] != serviceName {
		t.Fatalf("hello: code=%d body=%v", code, body)
	}
}

func TestMetricsExposesPrometheus(t *testing.T) {
	do(t, "/hello")
	code, _, raw := do(t, "/metrics")
	if code != http.StatusOK || !strings.Contains(raw, "golden_hello_requests_total") {
		t.Fatalf("metrics: code=%d", code)
	}
}
