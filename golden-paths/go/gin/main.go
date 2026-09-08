// Golden path — Go / Gin (B153). The most popular Go web framework. Contract: /health /ready /metrics
// /hello. Scaffold FROM it: scripts/new-service.sh go/gin <your-service>.
package main

import (
	"github.com/gin-gonic/gin"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

const serviceName = "golden-go-gin"

var helloHits = prometheus.NewCounter(prometheus.CounterOpts{
	Name: "golden_hello_requests_total",
	Help: "Calls to the demo /hello endpoint",
})

func init() { prometheus.MustRegister(helloHits) }

// Router builds the contract engine (implements http.Handler, so tests drive it with httptest).
func Router() *gin.Engine {
	gin.SetMode(gin.ReleaseMode)
	r := gin.New()
	r.GET("/health", func(c *gin.Context) { c.JSON(200, gin.H{"status": "ok"}) })
	r.GET("/ready", func(c *gin.Context) { c.JSON(200, gin.H{"status": "ready"}) })
	r.GET("/hello", func(c *gin.Context) {
		helloHits.Inc()
		c.JSON(200, gin.H{"service": serviceName, "message": "hello, weyland"})
	})
	r.GET("/metrics", gin.WrapH(promhttp.Handler()))
	return r
}

func main() {
	_ = Router().Run(":8080")
}
