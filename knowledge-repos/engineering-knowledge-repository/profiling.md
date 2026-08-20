---
id: profiling
tags: [methodology, performance, backend, frontend]
surfaces-at: [application-design, functional-design]
related: [apm, query-optimization, web-performance, load-testing, memory-management]
complexity: intermediate
---

# Profiling

## What It Is
The process of measuring where a program spends its time (CPU profiling) or allocates memory (memory profiling) to identify performance bottlenecks. Profiling produces data about which functions are called most frequently, how long each takes, and where memory is allocated or retained — turning "the application is slow" into "this specific function accounts for 40% of request latency." Profiling is the correct approach to performance optimization: measure first, optimize second. Guessing at bottlenecks without data produces optimizations that don't matter.

## When to Apply
- Before any performance optimization work — profile first to find the real bottleneck
- When APM shows a service is slow but doesn't identify the root cause at code level
- When memory usage is growing unexpectedly (memory leak investigation)
- As part of load testing — profile under realistic load to find bottlenecks that only appear at scale

## Key Concepts
- **CPU Profiling**: Measures where execution time is spent. Two approaches:
  - *Sampling profiler*: Periodically interrupts the program and records the current call stack. Low overhead; produces statistical approximation. Most production profilers use sampling
  - *Instrumentation profiler*: Adds timing instrumentation to every function call. Precise but high overhead; changes timing characteristics
- **Flame Graphs**: The standard visualization for profiling data. The x-axis is time (width = proportion of total time); the y-axis is call stack depth. Wide boxes at the top are the hottest code paths. Invented by Brendan Gregg; supported by all major profiling tools
- **Memory Profiling**: Tracks heap allocations — which code paths allocate the most memory, where objects are retained (preventing garbage collection). Essential for diagnosing memory leaks and excessive GC pressure
- **Language-Specific Tools**:
  - *Python*: `cProfile` + `snakeviz` for CPU; `memory_profiler`, `tracemalloc` for memory; `py-spy` for sampling production processes without restart
  - *Node.js*: V8 profiler via `--prof` flag; Chrome DevTools CPU profiler; `clinic.js` for production profiling
  - *Go*: `pprof` built into the standard library. Expose `/debug/pprof` endpoint; download profiles and view with `go tool pprof` or web UI
  - *Java/JVM*: JVM Flight Recorder (JFR); async-profiler; YourKit; VisualVM
  - *Browser JavaScript*: Chrome DevTools Performance tab — CPU flame charts, memory snapshots, allocation timelines
- **Continuous Profiling**: Production profiling running continuously with minimal overhead. Samples stack traces across time; identifies performance regressions between deploys. Tools: Datadog Continuous Profiler, Pyroscope (open source), Google Cloud Profiler. Increasingly standard for high-traffic services
- **GC Pressure**: Garbage collection pauses are a performance issue in managed-runtime languages (Python, Java, Go, Node.js). Memory profiling identifies excessive object creation that triggers frequent GC. Solutions: object pooling, reducing allocations in hot paths, tuning GC parameters
- **Profiling in Production vs. Development**:
  - Development profiling: full instrumentation, detailed output, acceptable overhead
  - Production profiling: sampling profilers with < 1-2% overhead. `py-spy`, `async-profiler`, and `pprof` are designed for production use
- **Common Findings**:
  - Serialization/deserialization in hot paths (JSON parsing on every request)
  - Unnecessary copies of large data structures
  - N+1 database queries (also visible in APM traces)
  - Inefficient algorithms with poor complexity (O(n²) in a tight loop)
  - GC pressure from short-lived object creation
  - Blocking I/O on the main thread

## In Practice
Method uses `py-spy` for production Python profiling (attaches to running processes without restart), `pprof` for Go services, and async-profiler for JVM services. Datadog Continuous Profiler is enabled on high-traffic services. Chrome DevTools profiler is used for frontend JavaScript performance work. Profiling is required before any significant performance optimization work — optimization without measurement is prohibited.

## Engineering Knowledge Statement
💡 **Engineering Knowledge — Profiling**: Never optimize without profiling first — the bottleneck is almost never where you think it is. Flame graphs are the most efficient way to read profiling output: find the widest box in the upper half of the graph, that's where to focus. Use sampling profilers in production (`py-spy`, `pprof`, `async-profiler`) — they add < 1-2% overhead and attach to running processes without restart. Continuous profiling (Datadog, Pyroscope) catches performance regressions between deploys that you'd otherwise only notice through APM latency increases. GC pressure is the silent performance killer in managed runtimes — memory profiling surfaces it. → `engineering-knowledge-repository/profiling.md`

## Related Entries
- [APM](apm.md) — APM shows which services and endpoints are slow; profiling shows why at the code level
- [Query Optimization](query-optimization.md) — database query performance is often the top profiling finding for backend services
- [Web Performance](web-performance.md) — browser profiling tools diagnose JavaScript execution bottlenecks
- [Load Testing](load-testing.md) — profile under load to find bottlenecks that only emerge at realistic concurrency
