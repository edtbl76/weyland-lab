import TokamakShim
import GoldenTokamakUI

/// @main entry mounted into the DOM by TokamakDOM's reconciler. `carton bundle` builds this product
/// to `Bundle/` (index.html + <hash>.wasm + JS glue) — the headless web-bundle smoke, the client
/// analogue of a service golden path's run-to-completion k8s Job.
@main
struct GoldenApp: App {
  var body: some Scene {
    WindowGroup("golden") { GreetingView() }
  }
}
