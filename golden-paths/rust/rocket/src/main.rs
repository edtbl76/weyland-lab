//! Golden path — Rust / Rocket (B153). Runnable, ephemeral, extendable. Conforms to the golden-path
//! contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello. Binds 0.0.0.0:8080 via
//! ROCKET_ADDRESS/ROCKET_PORT (set in the Dockerfile). Scaffold: scripts/new-service.sh rust/rocket <name>.
#[macro_use]
extern crate rocket;

use std::sync::LazyLock;

use prometheus::{register_counter, Counter, Encoder, TextEncoder};
use rocket::serde::json::{json, Value};

const SERVICE_NAME: &str = "golden-rust-rocket";

static HELLO_HITS: LazyLock<Counter> =
    LazyLock::new(|| register_counter!("golden_hello_requests_total", "Calls to the demo /hello endpoint").unwrap());

#[get("/health")]
fn health() -> Value {
    json!({"status": "ok"})
}

#[get("/ready")]
fn ready() -> Value {
    json!({"status": "ready"})
}

#[get("/hello")]
fn hello() -> Value {
    HELLO_HITS.inc();
    json!({"service": SERVICE_NAME, "message": "hello, weyland"})
}

#[get("/metrics")]
fn metrics() -> String {
    let mut buf = Vec::new();
    TextEncoder::new().encode(&prometheus::gather(), &mut buf).unwrap();
    String::from_utf8(buf).unwrap_or_default()
}

/// Builds the Rocket instance — shared by launch and the tests.
fn build() -> rocket::Rocket<rocket::Build> {
    rocket::build().mount("/", routes![health, ready, hello, metrics])
}

#[launch]
fn rocket() -> _ {
    build()
}

#[cfg(test)]
mod tests {
    use super::*;
    use rocket::http::Status;
    use rocket::local::blocking::Client;

    #[test]
    fn health_is_ok() {
        let client = Client::tracked(build()).unwrap();
        let resp = client.get("/health").dispatch();
        assert_eq!(resp.status(), Status::Ok);
        let body: serde_json::Value = resp.into_json().unwrap();
        assert_eq!(body["status"], "ok");
    }

    #[test]
    fn ready_is_ready() {
        let client = Client::tracked(build()).unwrap();
        let body: serde_json::Value = client.get("/ready").dispatch().into_json().unwrap();
        assert_eq!(body["status"], "ready");
    }

    #[test]
    fn hello_returns_known_payload() {
        let client = Client::tracked(build()).unwrap();
        let body: serde_json::Value = client.get("/hello").dispatch().into_json().unwrap();
        assert_eq!(body["message"], "hello, weyland");
        assert_eq!(body["service"], SERVICE_NAME);
    }

    #[test]
    fn metrics_exposes_prometheus() {
        let client = Client::tracked(build()).unwrap();
        client.get("/hello").dispatch();
        let body = client.get("/metrics").dispatch().into_string().unwrap();
        assert!(body.contains("golden_hello_requests_total"));
    }

    #[test]
    #[ignore]
    fn deliberate_failure() {
        panic!("selfcheck: the golden-path rust lane must surface this failure (exit non-zero)");
    }
}
