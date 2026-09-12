import NIOConcurrencyHelpers

/// Minimal, valid Prometheus text-exposition backend for the golden-path contract.
///
/// swift-prometheus is optional per the contract; a single counter matching the estate's
/// `golden_hello_requests_total` (the go exemplar's metric) is enough to prove `/metrics`
/// serves a scrapeable exposition. Thread-safe via a NIO locked value box.
public final class HelloCounter: Sendable {
    public static let shared = HelloCounter()

    private let hits = NIOLockedValueBox<Int>(0)

    private init() {}

    public func increment() {
        hits.withLockedValue { $0 += 1 }
    }

    public func value() -> Int {
        hits.withLockedValue { $0 }
    }

    /// Prometheus text exposition (version 0.0.4) for the demo counter.
    public func exposition() -> String {
        """
        # HELP golden_hello_requests_total Calls to the demo /hello endpoint
        # TYPE golden_hello_requests_total counter
        golden_hello_requests_total \(value())
        """
    }
}
