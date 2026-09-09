# Golden path — PHP / Slim

Blessed paved-road Slim 4 service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
composer install && vendor/bin/phpunit --exclude-group selfcheck   # 4 contract tests (app driven in-process)
vendor/bin/phpunit --group selfcheck                               # the deliberate failure (proves the lane propagates)
bash scripts/run-lang-tests.sh php                                 # the CI lane runs this golden path
```

Layout: `composer.json` (Slim + slim/psr7; phpunit + phpstan dev); `src/app.php` returns the configured
Slim app (reused by `public/index.php` to serve and by `tests/` to drive in-process); served via the PHP
built-in server (`php -S ... public/index.php`). Metrics = a Prometheus text endpoint at `/metrics` (a
real service swaps in promphp/prometheus_client_php with an APCu/Redis store).

**Ephemeral Job + scaffolding + the onboarding declaration** work as the Python FastAPI reference — see
[../../python/fastapi/README.md](../../python/fastapi/README.md) and `scripts/run-golden-path-jobs.sh`
(reads `.smoke`). Scaffold: `scripts/new-service.sh php/slim <your-service>`.
