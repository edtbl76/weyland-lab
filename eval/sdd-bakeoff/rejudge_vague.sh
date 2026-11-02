#!/usr/bin/env bash
# Validate the reason-aware vague judge on the 4 references, then re-judge all 10 vague results (round 1 + follow-on)
# in CI's shell-tests image. → results/vague-<arm>.judge, results2/vague-<arm>.judge, stdout summary.
set -uo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
R=$C/reference
judge() {  # <repo> <mode>
  docker run --rm -v "$1":/src:ro -v "$R/judge-vague":/j:ro --entrypoint sh bats/bats:latest -c \
    'apk add --no-cache python3 py3-yaml jq git prometheus >/dev/null 2>&1; cp -r /src /w && git config --global --add safe.directory /w && cd /w && python3 /j/judge.py /w "$(git rev-list --max-parents=0 HEAD)" '"$2"
}
echo "== validation"
for t in "ref-vague-base:round1:FAIL" "ref-vague-r1:round1:PASS" "ref-vague-r1:followon:FAIL" "ref-vague-f:followon:PASS"; do
  IFS=: read -r d m want <<< "$t"
  got=$(judge "$R/$d" "$m" 2>&1 | grep "JUDGE:")
  echo "$d $m (want $want): $got"
done
echo "== round 1"
for a in none aidlc bmad openspec speckit; do
  judge "$B/trials/vague-$a" round1 > "$B/results/vague-$a.judge" 2>&1
  echo "$a: $(tail -1 "$B/results/vague-$a.judge")"
done
echo "== follow-on"
for a in none aidlc bmad openspec speckit; do
  judge "$B/trials2/vague-$a" followon > "$B/results2/vague-$a.judge" 2>&1
  echo "$a: $(tail -1 "$B/results2/vague-$a.judge")"
done
