<?php
// Serve the golden-path Slim app. Run via the PHP built-in server as a router script:
//   php -S 0.0.0.0:8080 -t public public/index.php
declare(strict_types=1);

/** @var \Slim\App $app */
$app = require __DIR__ . '/../src/app.php';
$app->run();
