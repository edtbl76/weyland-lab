// Deliberately-failing test — proves the dotnet lane PROPAGATES failure. It carries the
// `Category=selfcheck` trait, so a normal run (`dotnet test --filter Category!=selfcheck`) never sees
// it and the lane self-check (`--filter Category=selfcheck`) runs ONLY it. Filtering on a stable trait
// (not a test NAME) is the .NET analogue of the go build tag / the Surefire selfcheck profile: removing
// the trait doesn't silently retire the test — it starts failing the NORMAL run, which is loud.
using Xunit;

public class DeliberateTests
{
    [Fact]
    [Trait("Category", "selfcheck")]
    public void Deliberate_failure()
    {
        Assert.Fail("selfcheck: the golden-path dotnet lane must surface this failure (exit non-zero)");
    }
}
