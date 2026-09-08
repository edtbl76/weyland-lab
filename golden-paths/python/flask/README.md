# Golden path — Python / flask

Blessed paved-road flask service. **Runnable · ephemeral · extendable.** Conforms to the golden-path
contract ([docs/design/golden-paths.md](../../../docs/design/golden-paths.md)): `/health` `/ready`
`/metrics` `/hello`.

```
pip install -r requirements.txt
gunicorn -b 127.0.0.1:8080 main:app          # run locally
bash scripts/run-lang-tests.sh python              # the CI lane runs this golden path's tests
```

**Ephemeral Job + scaffolding + the onboarding declaration** work exactly as the FastAPI reference —
see [../fastapi/README.md](../fastapi/README.md) (the applications.yaml / apis.yaml / LikeC4 template a
scaffolded service fills) and `scripts/run-golden-path-jobs.sh`. `smoke.py` starts the real server and
asserts `/ready`+`/hello`. Scaffold: `scripts/new-service.sh python/flask <your-service>`.
