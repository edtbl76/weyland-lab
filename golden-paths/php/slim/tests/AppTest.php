<?php
// Golden-path contract tests — drive the REAL Slim app in-process (no server).
declare(strict_types=1);

use PHPUnit\Framework\TestCase;
use Slim\Psr7\Factory\ServerRequestFactory;

final class AppTest extends TestCase
{
    /** @return array{0: int, 1: string} */
    private function get(string $path): array
    {
        /** @var \Slim\App $app */
        $app = require __DIR__ . '/../src/app.php';
        $request = (new ServerRequestFactory())->createServerRequest('GET', $path);
        $response = $app->handle($request);
        return [$response->getStatusCode(), (string) $response->getBody()];
    }

    public function testHealthIsOk(): void
    {
        [$status, $body] = $this->get('/health');
        self::assertSame(200, $status);
        self::assertStringContainsString('ok', $body);
    }

    public function testReadyIsReady(): void
    {
        [$status, $body] = $this->get('/ready');
        self::assertSame(200, $status);
        self::assertStringContainsString('ready', $body);
    }

    public function testHelloReturnsKnownPayload(): void
    {
        [$status, $body] = $this->get('/hello');
        self::assertSame(200, $status);
        self::assertStringContainsString('hello, weyland', $body);
        self::assertStringContainsString('golden-php-slim', $body);
    }

    public function testMetricsExposesPrometheus(): void
    {
        [$status, $body] = $this->get('/metrics');
        self::assertSame(200, $status);
        self::assertStringContainsString('golden_hello_requests', $body);
    }
}
