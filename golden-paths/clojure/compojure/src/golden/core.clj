(ns golden.core
  "Golden-path contract via Compojure routes over Ring, served by Jetty."
  (:require [compojure.core :refer [defroutes GET]]
            [compojure.route :as route]
            [ring.adapter.jetty :refer [run-jetty]]
            [cheshire.core :as json])
  (:gen-class))

(def service "golden-clojure-compojure")

(defn- json-resp [data]
  {:status 200
   :headers {"Content-Type" "application/json"}
   :body (json/generate-string data)})

(def metrics-body
  ;; Prometheus text exposition, hand-rolled to stay dependency-free.
  (str "# HELP golden_hello_requests_total Calls to /hello\n"
       "# TYPE golden_hello_requests_total counter\n"
       "golden_hello_requests_total 0\n"))

(defroutes app
  (GET "/health" [] (json-resp {:status "ok"}))
  (GET "/ready" [] (json-resp {:status "ready"}))
  (GET "/hello" [] (json-resp {:service service :message "hello, weyland"}))
  (GET "/metrics" []
    {:status 200
     :headers {"Content-Type" "text/plain; version=0.0.4"}
     :body metrics-body})
  (route/not-found "not found"))

(defn -main [& _args]
  (let [port (Integer/parseInt (or (System/getenv "PORT") "8080"))]
    (run-jetty app {:port port :join? true})))
