# Task: a private model lane that can never reach a hosted provider, with a CI guard

**Repo:** this repository (a homelab platform). **Area:** the LiteLLM gateway config
`nodes/mother/lab/weyland-platform/k8s/litellm/configmap.yaml`, plus `scripts/` and `scripts/tests/`.

**Problem.** The gateway's local lanes (e.g. `wl-rag`) are self-hosted Ollama on the LAN host `192.168.1.230`, but
`router_settings.fallbacks` sends them to hosted providers when Ollama is down. So no lane can be trusted with private
data: a fallback is silent. Background: `docs/backlog.md` item B234.

**Required behaviour.**
1. Add two private aliases to the LiteLLM `model_list`: `wl-private-rag` (Ollama model `gpt-oss:20b`) and
   `wl-private-reason` (Ollama model `qwen3:30b-a3b`), both served ONLY by Ollama on `http://192.168.1.230:11434`, with
   no fallback of any kind. Leave every existing alias's behaviour unchanged.
2. Add a guard, `scripts/check-private-lanes.py`, run as `python3 scripts/check-private-lanes.py <path-to-configmap.yaml>`.
   It reads the LiteLLM config embedded in the ConfigMap (`data."config.yaml"`) and exits:
   - **0** when every `wl-private-*` alias is safe;
   - **1** when any `wl-private-*` alias could reach something other than self-hosted Ollama on an allowed LAN host. That
     includes at least: a deployment whose model is not `ollama/` or `ollama_chat/`; an `api_base` host not on the
     allowlist (only `192.168.1.230` today); a `fallbacks`, `context_window_fallbacks` or `content_policy_fallbacks` rule
     (in `router_settings` or `litellm_settings`) taking a private alias to a non-private alias; a router-wide
     `default_fallbacks` with a non-private target (it applies to every alias); a wildcard `model_name` (such as `wl-*`
     or `*`) that would match a private name; a `model_group_alias` entry that maps a private name elsewhere. A fallback
     from one private alias to ANOTHER private alias is allowed;
   - **2** when it cannot check: the file is unreadable or malformed, or the config has no `wl-private-*` alias at all
     (a guard that checks nothing must not pass).
3. Add tests for the guard under `scripts/tests/` (bats), and wire the guard into CI's `repo-guards` step in
   `.woodpecker.yml` so it runs on every pipeline against the real configmap.

**Acceptance criteria.**
- [ ] The real configmap has both private aliases, and the guard exits 0 on it.
- [ ] The guard exits 1 for each unsafe case listed above, and 2 for an unreadable file or a config with no private alias.
- [ ] The guard has tests and runs in CI's repo-guards step.

**Tools available on PATH:** `bats`, `python3` (with PyYAML).
