(defproject golden-compojure "0.1.0"
  ;; Golden path — Clojure / Ring + Compojure (B160). The idiomatic Clojure web stack: the Compojure
  ;; routing DSL over Ring, served by Jetty. Contract: /health /ready /metrics /hello.
  :description "Golden path — Clojure / Ring + Compojure"
  :dependencies [[org.clojure/clojure "1.12.0"]
                 [ring/ring-core "1.12.2"]
                 [ring/ring-jetty-adapter "1.12.2"]
                 [compojure "1.7.1"]
                 [cheshire "5.13.0"]]
  :main golden.core
  :aot [golden.core]
  :uberjar-name "golden-compojure-standalone.jar"
  :profiles {:dev {:dependencies [[ring/ring-mock "0.4.0"]]}}
  ;; The deliberately-failing test carries ^:selfcheck; the :default selector excludes it from a normal
  ;; `lein test`, and `lein test :selfcheck` runs ONLY it. Metadata-based → fail-closed on a rename.
  :test-selectors {:default (complement :selfcheck)
                   :selfcheck :selfcheck})
