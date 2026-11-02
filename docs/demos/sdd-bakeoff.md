# Demo: the SDD framework bake-off harness (B86)

The harness that measured AI-DLC, BMAD, OpenSpec and Spec Kit against plain Claude Code
([verdict](../concepts/spec-driven-frameworks.md), [runbook](../runbooks/sdd-frameworks.md),
[flow](../diagrams/flow-sdd-bakeoff.md)). It is repo tooling with no UI, so the CLI walkthrough is the whole demo
(DoD, "Applying this to repo tooling"). Every step below is free (no agent run, no usage) and was RUN on 2026-11-02.

## 1. Self-test: the decisions that went wrong during the bake-off, pinned

[rogueone]
```
docker run --rm -v /home/edwardmangini/IdeaProjects/weyland:/r:ro -w /r --entrypoint sh bats/bats:latest -c 'apk add --no-cache python3 py3-yaml jq git >/dev/null 2>&1; bats scripts/tests/sdd-bakeoff.bats'
```

Expected (RUN):

```
1..11
ok 1 an undriven log: cost is the LAST result (cumulative), turns are summed
ok 2 a driven log is counted only up to its first final status
ok 3 a gate question that mentions TRIAL BLOCKED is not a final status
ok 4 driver: replies until TRIAL DONE, then stops
ok 5 driver: a final TRIAL BLOCKED stops it (no 15 wasted replies)
ok 6 driver: a reply that changes nothing stops it
ok 7 driver: every other arm gets the single prompt only
ok 8 intent oracle: a vague trial with no own tests found is never 'own tests pass'
ok 9 oracle scoring: a review with no DEFECT LINE is a miss, a bolded one parses
ok 10 ablation: a base judge whose LAST verdict is FAIL does not exclude the pair
ok 11 statistics: McNemar, sign-flip, Holm and the stratified permutation are exact
```

The driver tests run `run_trial.sh` against a stub `claude` (`CLAUDE_BIN`), so they spend nothing.

## 2. Negative case: the guard fails when the fix is removed

Delete the driver's "stop on a final TRIAL BLOCKED" line in a throwaway copy inside the container, then run the
driver tests. The repo is mounted read-only and is not changed.

[rogueone]
```
docker run --rm -v /home/edwardmangini/IdeaProjects/weyland:/r:ro --entrypoint sh bats/bats:latest -c 'apk add --no-cache python3 py3-yaml jq git >/dev/null 2>&1; mkdir -p /w/eval /w/scripts/tests; cp -r /r/eval/sdd-bakeoff /w/eval/; cp /r/scripts/tests/sdd-bakeoff.bats /w/scripts/tests/; sed -i "/grep -q \"TRIAL BLOCKED\" \&\& !/d" /w/eval/sdd-bakeoff/run_trial.sh; cd /w && bats -f driver scripts/tests/sdd-bakeoff.bats; echo "exit=$?"'
```

Expected (RUN): exactly the test for that rule fails, and bats exits non-zero.

```
1..4
ok 1 driver: replies until TRIAL DONE, then stops
not ok 2 driver: a final TRIAL BLOCKED stops it (no 15 wasted replies)
ok 3 driver: a reply that changes nothing stops it
ok 4 driver: every other arm gets the single prompt only
exit=1
```

## 3. Reproduce the published statistics from the stored results

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/analyze.py | sed -n '/^COST/,/^$/p'
```

Expected (RUN; about 3 minutes, every permutation is enumerated):

```
COST (effect = framework/none cost ratio); exact stratified permutation, Holm over 5 arms
  aidlc        x4.59  p=0.0000  holm=0.0001  (n 12 vs 12)
  bmad         x2.58  p=0.0000  holm=0.0001  (n 12 vs 12)
  openspec     x1.35  p=0.0061  holm=0.0061  (n 12 vs 12)
  speckit      x1.64  p=0.0000  holm=0.0001  (n 12 vs 12)
  aidlc211    x10.91  p=0.0000  holm=0.0001  (n 12 vs 12)
  AI-DLC 2.11.2 vs 2.6.18:    x2.37  p=0.0000  (n 12 vs 12; one planned comparison)
```

The repo copy of the harness reproduced `results/analysis.txt` byte for byte (2026-11-02), and also every judge
verdict and layer-1 quality report it was checked on.

## 4. Prove a framework's engine actually ran

[rogueone]
```
python3 /home/edwardmangini/IdeaProjects/weyland/eval/sdd-bakeoff/engine_calls.py /home/edwardmangini/sdd-bakeoff/results/small-openspec.jsonl 'openspec (new|status|instructions|validate|archive)'
```

Expected (RUN): `5 matching call(s)`, the first being `openspec new change "fail-unquoted-alert-series-values"`, which
answers `Created change ...`. On Node 18 that same call crashed with `SyntaxError: Unexpected token 'with'`, and the
run still passed; this check is what tells the two apart.

## Cleanup

Read-only. Step 1 writes only to the bats temp dir, and step 2 only inside the throwaway container. Steps 3 and 4
read the work dir; step 3 rewrites `results/analysis.txt` with identical content.
