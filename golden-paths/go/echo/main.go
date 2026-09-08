// Golden path — Go / Echo (B153). Ergonomic, performant. Contract: /health /ready /metrics /hello.
// Scaffold FROM it: scripts/new-service.sh go/echo <your-service>.
package main

import (
	"net/http"

	"github.com/labstack/echo/v4"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

const serviceName = "golden-go-echo"

var helloHits = prometheus.NewCounter(prometheus.CounterOpts{
	Name: "golden_hello_requests_total",
	Help: "Calls to the demo /hello endpoint",
})

func init() { prometheus.MustRegister(helloHits) }

// Router builds the contract server (implements http.Handler, so tests drive it with httptest).
func Router() *echo.Echo {
	e := echo.New()
	e.HideBanner = true
	e.HidePort = true
	e.GET("/health", func(c echo.Context) error { return c.JSON(http.StatusOK, map[string]string{"status": "ok"}) })
	e.GET("/ready", func(c echo.Context) error { return c.JSON(http.StatusOK, map[string]string{"status": "ready"}) })
	e.GET("/hello", func(c echo.Context) error {
		helloHits.Inc()
		return c.JSON(http.StatusOK, map[string]string{"service": serviceName, "message": "hello, weyland"})
	})
	e.GET("/metrics", echo.WrapHandler(promhttp.Handler()))
	return e
}

func main() {
	e := Router()
	e.Logger.Fatal(e.Start(":8080"))
}
