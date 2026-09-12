import TokamakShim

/// The framework-agnostic golden-path contract, expressed as a SwiftUI-shaped view tree.
/// The two tokens are the client analogue of the service paths' `/hello` JSON
/// (`{"service":"golden-swift-tokamak","message":"hello, weyland"}`): here they are rendered
/// declaratively into the DOM rather than served over HTTP.
public struct GreetingView: View {
  public static let service = "golden-swift-tokamak"
  public static let message = "hello, weyland"
  public init() {}
  public var body: some View {
    VStack {
      Text(GreetingView.message)
      Text(GreetingView.service)
    }
  }
}
