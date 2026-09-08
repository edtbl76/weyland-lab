//! Golden path — Rust / Axum (B153). Runnable, ephemeral, extendable. Conforms to the golden-path
//! contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
//! Scaffold FROM it: scripts/new-service.sh rust/axum <your-service>.
use std::sync::LazyLock;

use axum::http::header;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use prometheus::{register_counter, Counter, Encoder, TextEncoder};
use serde_json::json;

const SERVICE_NAME: &str = "golden-rust-axum";

static HELLO_HITS: LazyLock<Counter> =
    LazyLock::new(|| register_counter!("golden_hello_requests_total", "Calls to the demo /hello endpoint").unwrap());

async fn health() -> impl IntoResponse {
    Json(json!({"status": "ok"}))
}

async fn ready() -> impl IntoResponse {
    Json(json!({"status": "ready"}))
}

async fn hello() -> impl IntoResponse {
    HELLO_HITS.inc();
    Json(json!({"service": SERVICE_NAME, "message": "hello, weyland"}))
}

async fn metrics() -> impl IntoResponse {
    let mut buf = Vec::new();
    TextEncoder::new().encode(&prometheus::gather(), &mut buf).unwrap();
    ([(header::CONTENT_TYPE, "text/plain; version=0.0.4")], buf)
}

pub fn router() -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/ready", get(ready))
        .route("/hello", get(hello))
        .route("/metrics", get(metrics))
}

#[tokio::main]
async fn main() {
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await.unwrap();
    axum::serve(listener, router()).await.unwrap();
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::body::Body;
    use axum::http::{Request, StatusCode};
    use tower::ServiceExt; // for `oneshot`

    async fn get_json(path: &str) -> (StatusCode, serde_json::Value) {
        let resp = router()
            .oneshot(Request::builder().uri(path).body(Body::empty()).unwrap())
            .await
            .unwrap();
        let status = resp.status();
        let bytes = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
        (status, serde_json::from_slice(&bytes).unwrap_or(serde_json::Value::Null))
    }

    #[tokio::test]
    async fn health_is_ok() {
        let (s, b) = get_json("/health").await;
        assert_eq!(s, StatusCode::OK);
        assert_eq!(b["status"], "ok");
    }

    #[tokio::test]
    async fn ready_is_ready() {
        let (s, b) = get_json("/ready").await;
        assert_eq!(s, StatusCode::OK);
        assert_eq!(b["status"], "ready");
    }

    #[tokio::test]
    async fn hello_returns_known_payload() {
        let (s, b) = get_json("/hello").await;
        assert_eq!(s, StatusCode::OK);
        assert_eq!(b["message"], "hello, weyland");
        assert_eq!(b["service"], SERVICE_NAME);
    }

    #[tokio::test]
    async fn metrics_exposes_prometheus() {
        get_json("/hello").await;
        let resp = router()
            .oneshot(Request::builder().uri("/metrics").body(Body::empty()).unwrap())
            .await
            .unwrap();
        let bytes = axum::body::to_bytes(resp.into_body(), usize::MAX).await.unwrap();
        assert!(String::from_utf8_lossy(&bytes).contains("golden_hello_requests_total"));
    }

    /// The rust lane self-check runs `cargo test -- --ignored`: `#[ignore]` keeps it out of a normal run.
    #[test]
    #[ignore]
    fn deliberate_failure() {
        panic!("selfcheck: the golden-path rust lane must surface this failure (exit non-zero)");
    }
}
