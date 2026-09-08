// Golden path — Go / net/http (stdlib) (B153).
//
// The idiomatic stdlib baseline. Runnable, ephemeral, extendable. Conforms to the golden-path contract
// (docs/design/golden-paths.md): GET /health /ready /metrics /hello. Scaffold FROM it:
// scripts/new-service.sh go/nethttp <your-service>.
package main

import (
	"encoding/json"
	"log"
	"net/http"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

const serviceName = "golden-go-nethttp"

var helloHits = prometheus.NewCounter(prometheus.CounterOpts{
	Name: "golden_hello_requests_total",
	Help: "Calls to the demo /hello endpoint",
})

func init() { prometheus.MustRegister(helloHits) }

func writeJSON(w http.ResponseWriter, v map[string]string) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}

// Router builds the contract mux. Exported (via package-level) so tests drive it with httptest.
func Router() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, _ *http.Request) { writeJSON(w, map[string]string{"status": "ok"}) })
	mux.HandleFunc("/ready", func(w http.ResponseWriter, _ *http.Request) { writeJSON(w, map[string]string{"status": "ready"}) })
	mux.HandleFunc("/hello", func(w http.ResponseWriter, _ *http.Request) {
		helloHits.Inc()
		writeJSON(w, map[string]string{"service": serviceName, "message": "hello, weyland"})
	})
	mux.Handle("/metrics", promhttp.Handler())
	return mux
}

func main() {
	log.Printf(`{"service":%q,"msg":"listening on :8080"}`, serviceName)
	log.Fatal(http.ListenAndServe(":8080", Router())) //nolint:gosec // golden-path template; a real service sets timeouts
}
