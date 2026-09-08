//! Golden path — Rust / Actix-web (B153). Runnable, ephemeral, extendable. Conforms to the golden-path
//! contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello.
//! Scaffold FROM it: scripts/new-service.sh rust/actix <your-service>.
use std::sync::LazyLock;

use actix_web::{web, App, HttpResponse, HttpServer, Responder};
use prometheus::{register_counter, Counter, Encoder, TextEncoder};
use serde_json::json;

const SERVICE_NAME: &str = "golden-rust-actix";

static HELLO_HITS: LazyLock<Counter> =
    LazyLock::new(|| register_counter!("golden_hello_requests_total", "Calls to the demo /hello endpoint").unwrap());

async fn health() -> impl Responder {
    HttpResponse::Ok().json(json!({"status": "ok"}))
}

async fn ready() -> impl Responder {
    HttpResponse::Ok().json(json!({"status": "ready"}))
}

async fn hello() -> impl Responder {
    HELLO_HITS.inc();
    HttpResponse::Ok().json(json!({"service": SERVICE_NAME, "message": "hello, weyland"}))
}

async fn metrics() -> impl Responder {
    let mut buf = Vec::new();
    TextEncoder::new().encode(&prometheus::gather(), &mut buf).unwrap();
    HttpResponse::Ok().content_type("text/plain; version=0.0.4").body(buf)
}

/// Registers the contract routes — shared by `main` and the tests.
pub fn configure(cfg: &mut web::ServiceConfig) {
    cfg.route("/health", web::get().to(health))
        .route("/ready", web::get().to(ready))
        .route("/hello", web::get().to(hello))
        .route("/metrics", web::get().to(metrics));
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| App::new().configure(configure))
        .bind(("0.0.0.0", 8080))?
        .run()
        .await
}

#[cfg(test)]
mod tests {
    use super::*;
    use actix_web::App;

    #[actix_web::test]
    async fn health_is_ok() {
        let app = actix_web::test::init_service(App::new().configure(configure)).await;
        let body: serde_json::Value =
            actix_web::test::call_and_read_body_json(&app, actix_web::test::TestRequest::get().uri("/health").to_request()).await;
        assert_eq!(body["status"], "ok");
    }

    #[actix_web::test]
    async fn ready_is_ready() {
        let app = actix_web::test::init_service(App::new().configure(configure)).await;
        let body: serde_json::Value =
            actix_web::test::call_and_read_body_json(&app, actix_web::test::TestRequest::get().uri("/ready").to_request()).await;
        assert_eq!(body["status"], "ready");
    }

    #[actix_web::test]
    async fn hello_returns_known_payload() {
        let app = actix_web::test::init_service(App::new().configure(configure)).await;
        let body: serde_json::Value =
            actix_web::test::call_and_read_body_json(&app, actix_web::test::TestRequest::get().uri("/hello").to_request()).await;
        assert_eq!(body["message"], "hello, weyland");
        assert_eq!(body["service"], SERVICE_NAME);
    }

    #[actix_web::test]
    async fn metrics_exposes_prometheus() {
        let app = actix_web::test::init_service(App::new().configure(configure)).await;
        actix_web::test::call_and_read_body(&app, actix_web::test::TestRequest::get().uri("/hello").to_request()).await;
        let body = actix_web::test::call_and_read_body(&app, actix_web::test::TestRequest::get().uri("/metrics").to_request()).await;
        assert!(String::from_utf8_lossy(&body).contains("golden_hello_requests_total"));
    }

    #[test]
    #[ignore]
    fn deliberate_failure() {
        panic!("selfcheck: the golden-path rust lane must surface this failure (exit non-zero)");
    }
}
