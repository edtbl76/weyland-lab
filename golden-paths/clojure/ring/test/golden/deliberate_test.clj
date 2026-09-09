(ns golden.deliberate-test
  ;; Deliberately-failing test — proves the clojure lane PROPAGATES failure. It carries ^:selfcheck; the
  ;; :default test-selector (in project.clj) excludes it from a normal run and `lein test :selfcheck`
  ;; runs ONLY it. Metadata-based (not a name filter) → fail-closed on a rename.
  (:require [clojure.test :refer [deftest is]]))

(deftest ^:selfcheck deliberate-failure
  (is false "selfcheck: the golden-path clojure lane must surface this failure (exit non-zero)"))
