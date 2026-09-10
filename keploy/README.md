# Keploy — API-regression capture (B104)

Keploy records real inbound API traffic (via eBPF) and turns it into **committed** regression test-sets +
dependency mocks; `keploy test` replays them and diffs the responses. It is the record-from-traffic
complement to the hand-authored Bruno collection (`../bruno/weyland/`).

- **Config:** `keploy.yml` — targets a B160 golden-path image (self-contained, no deps).
- **Corpus:** `keploy/<test-set>/` (e.g. `keploy/golden-fastapi-smoke/`) — Keploy writes recordings to a
  `keploy/` subdir of the run dir, so from this folder they land at `keploy/keploy/<test-set>/`. The
  test-set is named by the `--metadata 'name=...'` you record with. Committed: `tests/` + `config.yaml` +
  `seed.sh`; `mocks.yaml` is gitignored (Keploy uploads mocks to its registry by hash on a green run).
- **Requires:** Linux kernel >= 5.10 + eBPF (privileged); **operator-on-demand**, never CI/scheduled.
- **How to run it:** [../docs/runbooks/api-client-bruno-keploy.md](../docs/runbooks/api-client-bruno-keploy.md).
