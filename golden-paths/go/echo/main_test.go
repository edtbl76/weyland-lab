// Golden-path self-test (Go/net/http) — the lane probe + contract proof, over httptest.
package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func get(t *testing.T, path string) (*httptest.ResponseRecorder, map[string]string) {
	t.Helper()
	rr := httptest.NewRecorder()
	Router().ServeHTTP(rr, httptest.NewRequest(http.MethodGet, path, nil))
	var body map[string]string
	_ = json.Unmarshal(rr.Body.Bytes(), &body)
	return rr, body
}

func TestHealthIsOK(t *testing.T) {
	rr, body := get(t, "/health")
	if rr.Code != http.StatusOK || body["status"] != "ok" {
		t.Fatalf("health: code=%d body=%v", rr.Code, body)
	}
}

func TestReadyIsReady(t *testing.T) {
	rr, body := get(t, "/ready")
	if rr.Code != http.StatusOK || body["status"] != "ready" {
		t.Fatalf("ready: code=%d body=%v", rr.Code, body)
	}
}

func TestHelloReturnsKnownPayload(t *testing.T) {
	rr, body := get(t, "/hello")
	if rr.Code != http.StatusOK || body["message"] != "hello, weyland" || body["service"] != serviceName {
		t.Fatalf("hello: code=%d body=%v", rr.Code, body)
	}
}

func TestMetricsExposesPrometheus(t *testing.T) {
	get(t, "/hello")
	rr := httptest.NewRecorder()
	Router().ServeHTTP(rr, httptest.NewRequest(http.MethodGet, "/metrics", nil))
	if rr.Code != http.StatusOK || !strings.Contains(rr.Body.String(), "golden_hello_requests_total") {
		t.Fatalf("metrics: code=%d", rr.Code)
	}
}
