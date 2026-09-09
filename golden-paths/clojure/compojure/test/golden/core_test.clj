(ns golden.core-test
  (:require [clojure.test :refer [deftest is]]
            [ring.mock.request :as mock]
            [golden.core :refer [app]]))

(deftest health-is-ok
  (let [resp (app (mock/request :get "/health"))]
    (is (= 200 (:status resp)))
    (is (re-find #"ok" (:body resp)))))

(deftest ready-is-ready
  (let [resp (app (mock/request :get "/ready"))]
    (is (= 200 (:status resp)))
    (is (re-find #"ready" (:body resp)))))

(deftest hello-returns-known-payload
  (let [resp (app (mock/request :get "/hello"))]
    (is (= 200 (:status resp)))
    (is (re-find #"hello, weyland" (:body resp)))
    (is (re-find #"golden-clojure-compojure" (:body resp)))))

(deftest metrics-exposes-prometheus
  (let [resp (app (mock/request :get "/metrics"))]
    (is (= 200 (:status resp)))
    (is (re-find #"golden_hello_requests" (:body resp)))))
