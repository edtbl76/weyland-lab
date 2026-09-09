(ns golden.core
  "Golden-path contract as a bare Ring handler (dispatch on :uri), served by Jetty."
  (:require [ring.adapter.jetty :refer [run-jetty]]
            [cheshire.core :as json])
  (:gen-class))

(def service "golden-clojure-ring")

(defn- json-resp [data]
  {:status 200
   :headers {"Content-Type" "application/json"}
   :body (json/generate-string data)})

(def metrics-body
  ;; Prometheus text exposition, hand-rolled to stay dependency-free.
  (str "# HELP golden_hello_requests_total Calls to /hello\n"
       "# TYPE golden_hello_requests_total counter\n"
       "golden_hello_requests_total 0\n"))

(defn app [req]
  (case (:uri req)
    "/health" (json-resp {:status "ok"})
    "/ready" (json-resp {:status "ready"})
    "/hello" (json-resp {:service service :message "hello, weyland"})
    "/metrics" {:status 200
                :headers {"Content-Type" "text/plain; version=0.0.4"}
                :body metrics-body}
    {:status 404 :headers {"Content-Type" "text/plain"} :body "not found"}))

(defn -main [& _args]
  (let [port (Integer/parseInt (or (System/getenv "PORT") "8080"))]
    (run-jetty app {:port port :join? true})))
