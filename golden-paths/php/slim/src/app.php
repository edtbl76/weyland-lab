<?php
// Golden path — PHP / Slim (B160).
//
// The idiomatic PHP micro-framework baseline. Runnable, ephemeral, extendable. Conforms to the
// golden-path contract (docs/design/golden-paths.md): GET /health /ready /metrics /hello. Scaffold FROM
// it: scripts/new-service.sh php/slim <your-service>.
//
// Returns the configured Slim app so both public/index.php (serve) and tests/ (drive in-process) reuse it.

declare(strict_types=1);

require_once __DIR__ . '/../vendor/autoload.php';

use Psr\Http\Message\ResponseInterface as Response;
use Psr\Http\Message\ServerRequestInterface as Request;
use Slim\Factory\AppFactory;

// define() with a guard, not `const`: app.php is re-required per test (to build a fresh app), and a
// top-level `const` would fatally redefine on the second require.
if (!defined('SERVICE_NAME')) {
    define('SERVICE_NAME', 'golden-php-slim');
}

$app = AppFactory::create();

$json = static function (Response $res, array $data): Response {
    $res->getBody()->write(json_encode($data, JSON_THROW_ON_ERROR));
    return $res->withHeader('Content-Type', 'application/json');
};

$app->get('/health', static fn (Request $req, Response $res): Response => $json($res, ['status' => 'ok']));
$app->get('/ready', static fn (Request $req, Response $res): Response => $json($res, ['status' => 'ready']));
$app->get('/hello', static fn (Request $req, Response $res): Response => $json($res, [
    'service' => SERVICE_NAME,
    'message' => 'hello, weyland',
]));
$app->get('/metrics', static function (Request $req, Response $res): Response {
    $body = "# HELP golden_hello_requests_total Calls to /hello\n"
        . "# TYPE golden_hello_requests_total counter\n"
        . "golden_hello_requests_total 0\n";
    $res->getBody()->write($body);
    return $res->withHeader('Content-Type', 'text/plain; version=0.0.4');
});

return $app;
