// Golden path — Go / Fiber (B153). Express-like, built on fasthttp (a distinct engine from the
// net/http trio). Contract: /health /ready /metrics /hello. Scaffold FROM it:
// scripts/new-service.sh go/fiber <your-service>.
package main

import (
	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/fiber/v2/middleware/adaptor"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

const serviceName = "golden-go-fiber"

var helloHits = prometheus.NewCounter(prometheus.CounterOpts{
	Name: "golden_hello_requests_total",
	Help: "Calls to the demo /hello endpoint",
})

func init() { prometheus.MustRegister(helloHits) }

// Router builds the contract app (fasthttp). Tests drive it with app.Test().
func Router() *fiber.App {
	app := fiber.New(fiber.Config{DisableStartupMessage: true})
	app.Get("/health", func(c *fiber.Ctx) error { return c.JSON(fiber.Map{"status": "ok"}) })
	app.Get("/ready", func(c *fiber.Ctx) error { return c.JSON(fiber.Map{"status": "ready"}) })
	app.Get("/hello", func(c *fiber.Ctx) error {
		helloHits.Inc()
		return c.JSON(fiber.Map{"service": serviceName, "message": "hello, weyland"})
	})
	app.Get("/metrics", adaptor.HTTPHandler(promhttp.Handler()))
	return app
}

func main() {
	_ = Router().Listen(":8080")
}
