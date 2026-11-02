#!/bin/sh
# Judge for the follow-on small change. Inside bats/bats with python3 py3-yaml prometheus: TRIAL=<repo> sh judge.sh
# PASS only if: (1) the ROUND-1 judge still passes (suite green + bare-hex plant refused), AND (2) a planted fixture
# with an empty-string series value makes its test FAIL.
set -u
J=$(dirname "$0")
echo "== round-1 regression"
sh "$J/../judge-small/judge.sh" > /tmp/r1.out 2>&1
r1=$?
tail -1 /tmp/r1.out
W=$(mktemp -d)
cp -r "$TRIAL/." "$W/"
cd "$W" || exit 2
cp "$J/empty-plant.test.yaml" scripts/tests/fixtures/alert-rules/empty-plant.test.yaml
printf '\n@test "JUDGE2 PLANT: an empty series value must not run silently" {\n  promtool_test empty-plant.test.yaml monitoring/blackbox-exporter.yaml\n}\n' >> scripts/tests/alert-rules.bats
echo "== empty-value plant"
bats -f "JUDGE2 PLANT" scripts/tests/alert-rules.bats > /tmp/p2.out 2>&1
p2=$?
head -6 /tmp/p2.out
if [ "$r1" -eq 0 ] && [ "$p2" -ne 0 ] && grep -q "^not ok" /tmp/p2.out; then
  echo "JUDGE: PASS (round-1 holds, empty plant refused)"; exit 0
fi
echo "JUDGE: FAIL (round-1 exit $r1, empty plant exit $p2)"; exit 1
