# Keploy — API-regression capture (B104)

Keploy records real inbound API traffic (via eBPF) and turns it into **committed** regression test-sets +
dependency mocks; `keploy test` replays them and diffs the responses. It is the record-from-traffic
complement to the hand-authored Bruno collection (`../bruno/weyland/`).

- **Config:** `keploy.yml` — targets a B160 golden-path image (self-contained, no deps).
- **Corpus:** `test-sets/` — recorded tests, committed to git (empty until the first record cycle).
- **Requires:** Linux kernel >= 5.10 + eBPF (privileged); **operator-on-demand**, never CI/scheduled.
- **How to run it:** [../docs/runbooks/api-client-bruno-keploy.md](../docs/runbooks/api-client-bruno-keploy.md).
