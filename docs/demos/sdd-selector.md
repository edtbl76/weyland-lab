# Demo: the SDD framework selector (B86.1)

A prompt or PRD in; a spec-driven framework, or none, out, with the reasons and the evidence
([runbook](../runbooks/sdd-frameworks.md#pick-a-framework-for-a-project-the-selector-b861),
[flow](../diagrams/flow-sdd-selector.md), [verdict it is calibrated on](../concepts/spec-driven-frameworks.md)).
Repo tooling with no UI, so the CLI walkthrough is the whole demo. Every step was RUN on 2026-11-02.

## 1. The decision logic, free (tests, no model)

[rogueone]
```
docker run --rm -v /home/edwardmangini/IdeaProjects/weyland/scripts:/s:ro python:3.12-slim sh -c 'pip install -q pyyaml==6.0.3 pytest==9.0.1 >/dev/null 2>&1; cp -r /s /w && cd /w && python -m pytest -q -p no:cacheprovider tests/test_select_sdd_framework.py'
```

Expected (RUN): `30 passed`. They pin:
- the picks the bake-off supports;
- the caveats for untested facts;
- unknowns listed and never filled;
- the three-read agreement rule;
- fail-closed extraction;
- the exit codes.

## 2. Live: a PRD for an area that keeps changing

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && LITELLM_API_BASE=http://192.168.1.243:30400 python3 /home/edwardmangini/IdeaProjects/weyland/scripts/select_sdd_framework.py /home/edwardmangini/IdeaProjects/weyland/scripts/tests/fixtures/sdd-selector/brownfield-recurring-prd.md
```

Expected (RUN, about 75 s, exit 0): `Pick: OpenSpec`, runner-up plain Claude Code, rule `repeated-change` with its two
evidence lines, and `Cost band: nearest measured task 'small': this pick $0.87 median, 3/3 passed; plain Claude Code
$0.48`.

The same command on `one-line-bug.md`, `brownfield-prd.md` (a one-off change), `vague-idea.md` and the four B86 task
briefs (`eval/sdd-bakeoff/reference/task-*.md`) gives `Pick: plain Claude Code (no framework)`. Each was run twice on
2026-11-02, and every pick was the same both times (16 of 16).

## 3. Negative case: no key, no recommendation

[rogueone]
```
env -u SDD_SELECTOR_LITELLM_KEY LITELLM_API_BASE=http://192.168.1.243:30400 python3 /home/edwardmangini/IdeaProjects/weyland/scripts/select_sdd_framework.py /home/edwardmangini/IdeaProjects/weyland/scripts/tests/fixtures/sdd-selector/one-line-bug.md; echo "exit=$?"
```

Expected (RUN):

```
no recommendation: SDD_SELECTOR_LITELLM_KEY is not set (the selector's own LiteLLM virtual key, in scripts/.env)
exit=2
```

It is never a default `none`: a failed read is not a recommendation.

## 4. The key is scoped to the private lane only

[rogueone]
```
set -a && . /home/edwardmangini/IdeaProjects/weyland/scripts/.env && set +a && for m in wl-private-rag wl-default; do curl -s -o /dev/null -w "$m %{http_code}\n" -m 300 -H "Authorization: Bearer $SDD_SELECTOR_LITELLM_KEY" -H 'Content-Type: application/json' -d "{\"model\":\"$m\",\"max_tokens\":200,\"messages\":[{\"role\":\"user\",\"content\":\"Reply with: ok\"}]}" http://192.168.1.243:30400/v1/chat/completions; done
```

Expected (RUN): `wl-private-rag 200`, `wl-default 403`.

## Cleanup

Read-only. The selector writes nothing; step 1 runs in a throwaway container. Step 2 loads `gpt-oss:20b` on rogueone,
so the operator's model reloads on its next call.
