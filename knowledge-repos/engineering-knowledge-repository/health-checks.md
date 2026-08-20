---
id: health-checks
tags: [pattern, infrastructure, reliability, backend]
surfaces-at: [application-design, infrastructure-design]
related: [load-balancing, circuit-breaker, kubernetes, auto-scaling]
complexity: foundational
---

# Health Checks

## What It Is
An endpoint or mechanism that allows infrastructure (load balancers, orchestrators, monitoring systems) to determine whether a service instance is alive and able to handle requests. A health check returns a simple pass/fail signal — healthy instances receive traffic; unhealthy instances are removed from rotation until they recover. Without health checks, traffic continues flowing to broken instances, causing errors for users. Health checks are the foundation of self-healing infrastructure.

## When to Apply
- Every service running behind a load balancer
- Any containerized service deployed on Kubernetes or ECS
- Services registered in a service mesh or service discovery system
- Any instance that should be automatically removed from rotation on failure

## Key Concepts
- **Liveness vs. Readiness**:
  - *Liveness*: Is the process alive? A failed liveness check restarts the container (Kubernetes). Checks for deadlocks, OOM states, or complete unresponsiveness
  - *Readiness*: Is the service ready to accept traffic? A failed readiness check removes the instance from load balancer rotation without restarting it. Checks for dependency availability, warm-up completion, or degraded state
  - *Startup*: Is the application done initializing? Kubernetes startup probes prevent premature liveness/readiness checks during slow startup
- **Shallow vs. Deep Checks**:
  - *Shallow*: Returns 200 if the process is running. Fast; low overhead; catches process crashes but not application-level failures
  - *Deep*: Validates database connectivity, cache availability, and key dependencies. More informative; risk of false positives if a dependency blips
- **Health Check Endpoint Convention**: `/health`, `/healthz`, `/ping`, `/status` — return HTTP 200 for healthy, 5xx for unhealthy. Include JSON body with component status for deep checks
- **Health Check Response Body**: For deep checks, return structured status per dependency:
  ```json
  {"status": "healthy", "checks": {"database": "ok", "cache": "ok", "queue": "degraded"}}
  ```
- **Kubernetes Probes**: Configure `livenessProbe`, `readinessProbe`, and `startupProbe` in pod specs. Set appropriate `initialDelaySeconds`, `periodSeconds`, `failureThreshold` based on application startup time
- **Load Balancer Integration**: AWS ALB, nginx, and HAProxy poll health endpoints at a configured interval. Failed checks remove the instance; successful checks after recovery re-add it
- **Circuit Breaker Relationship**: Health checks operate at the infrastructure level (is this instance alive?). Circuit breakers operate at the application level (is this dependency responding correctly?). Both are needed — health checks for instance management, circuit breakers for dependency management

## In Practice
Method services expose `/health` for liveness and `/health/ready` for readiness. Deep readiness checks validate database and cache connectivity. Kubernetes readiness probes use `/health/ready` with a 5-second period and 3-failure threshold. AWS ALB health checks hit `/health` with a 5-second timeout and 2-failure threshold. Health check endpoints are excluded from authentication middleware.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Health Checks**: Distinguish liveness (restart me) from readiness (stop sending me traffic) — conflating them causes unnecessary restarts during dependency blips. Deep health checks that check database connectivity are more useful than port checks, but design them to fail fast (short timeouts on dependency checks) to avoid cascading. Exclude health check endpoints from auth middleware — load balancers can't authenticate. In Kubernetes, tune `initialDelaySeconds` to account for actual startup time, or use a startup probe, to prevent liveness thrashing during slow initialization. → `engineering-knowledge-repository/health-checks.md`

## Related Entries
- [Load Balancing](load-balancing.md) — load balancers use health checks to manage instance pool membership
- [Circuit Breaker](circuit-breaker.md) — circuit breakers complement health checks for application-level dependency failure handling
- [Kubernetes](kubernetes.md) — Kubernetes liveness, readiness, and startup probes implement health check integration
- [Auto Scaling](auto-scaling.md) — auto scaling uses health check status to replace unhealthy instances
