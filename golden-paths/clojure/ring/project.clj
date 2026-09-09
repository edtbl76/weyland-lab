(defproject golden-ring "0.1.0"
  ;; Golden path — Clojure / Ring (B160). The lean baseline: a bare Ring handler dispatching on :uri,
  ;; no routing library — the lean sibling of the Compojure flagship. Contract: /health /ready /metrics /hello.
  :description "Golden path — Clojure / Ring (pure handler)"
  :dependencies [[org.clojure/clojure "1.12.0"]
                 [ring/ring-core "1.12.2"]
                 [ring/ring-jetty-adapter "1.12.2"]
                 [cheshire "5.13.0"]]
  :main golden.core
  :aot [golden.core]
  :uberjar-name "golden-ring-standalone.jar"
  :profiles {:dev {:dependencies [[ring/ring-mock "0.4.0"]]}}
  :test-selectors {:default (complement :selfcheck)
                   :selfcheck :selfcheck})
