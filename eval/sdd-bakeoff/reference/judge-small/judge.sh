#!/bin/sh
# Judge for the bake-off small fix. Run inside bats/bats with python3 py3-yaml prometheus installed:
#   TRIAL=<trial repo> sh judge.sh
# PASS only if (1) every existing alert-rules test passes, AND (2) the planted bare-hex fixture makes its test FAIL.
# The trial's own harness function (promtool_test) runs the plant, so whatever fix it made is what is judged.
set -u
W=$(mktemp -d)
cp -r "$TRIAL/." "$W/"
J=$(dirname "$0")
cd "$W" || exit 2
echo "== 1. existing suite"
bats scripts/tests/alert-rules.bats > /tmp/suite.out 2>&1
suite=$?
grep -E "^(ok|not ok)" /tmp/suite.out
cp "$J/hex-plant.test.yaml" scripts/tests/fixtures/alert-rules/hex-plant.test.yaml
printf '\n@test "JUDGE PLANT: a bare hex series value must not run silently" {\n  promtool_test hex-plant.test.yaml monitoring/blackbox-exporter.yaml\n}\n' >> scripts/tests/alert-rules.bats
echo "== 2. planted case"
bats -f "JUDGE PLANT" scripts/tests/alert-rules.bats > /tmp/plant.out 2>&1
plant=$?
cat /tmp/plant.out | head -8
if [ "$suite" -eq 0 ] && [ "$plant" -ne 0 ] && grep -q "^not ok" /tmp/plant.out; then
  echo "JUDGE: PASS (suite green, plant refused)"; exit 0
fi
echo "JUDGE: FAIL (suite exit $suite, plant exit $plant)"; exit 1
