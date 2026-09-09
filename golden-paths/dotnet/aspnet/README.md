# Golden path — C#/.NET / ASP.NET Core

Blessed paved-road ASP.NET Core minimal-API service. **Runnable · ephemeral · extendable.** Conforms to
the golden-path contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health`
`/ready` `/metrics` `/hello`.

```
dotnet test --filter Category!=selfcheck   # 4 contract tests (WebApplicationFactory, in-process) via golden.sln
dotnet test --filter Category=selfcheck    # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh dotnet      # the CI lane runs this golden path
```

Layout: `golden.sln` at the root ties two sibling projects — `App/` (`App.csproj` + `Program.cs`, the web
app, `AssemblyName=App` → `dotnet App.dll`) and `tests/` (xunit + `Microsoft.AspNetCore.Mvc.Testing`,
references `../App/App.csproj`). Metrics via `prometheus-net.AspNetCore` (`UseHttpMetrics` + `MapMetrics`).

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh dotnet/aspnet <your-service>`.
