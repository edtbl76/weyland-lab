// Golden-path contract tests — drive the REAL app in-process via WebApplicationFactory<Program>.
using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using Xunit;

public class ContractTests : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;

    public ContractTests(WebApplicationFactory<Program> factory) => _client = factory.CreateClient();

    [Fact]
    public async Task Health_is_ok()
    {
        var res = await _client.GetAsync("/health");
        Assert.Equal(HttpStatusCode.OK, res.StatusCode);
        Assert.Contains("\"status\":\"ok\"", await res.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Ready_is_ready()
    {
        var res = await _client.GetAsync("/ready");
        Assert.Equal(HttpStatusCode.OK, res.StatusCode);
        Assert.Contains("\"status\":\"ready\"", await res.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Hello_returns_the_known_payload()
    {
        var res = await _client.GetAsync("/hello");
        Assert.Equal(HttpStatusCode.OK, res.StatusCode);
        var body = await res.Content.ReadAsStringAsync();
        Assert.Contains("hello, weyland", body);
        Assert.Contains("golden-dotnet-aspnet", body);
    }

    [Fact]
    public async Task Metrics_exposes_prometheus()
    {
        // touch /hello first so the counter is present in the exposition
        await _client.GetAsync("/hello");
        var res = await _client.GetAsync("/metrics");
        Assert.Equal(HttpStatusCode.OK, res.StatusCode);
        Assert.Contains("golden_hello_requests_total", await res.Content.ReadAsStringAsync());
    }
}
