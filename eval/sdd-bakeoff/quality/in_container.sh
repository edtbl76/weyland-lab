#!/usr/bin/env bash
# Runs INSIDE a throwaway python:3.12-slim container on a COPY of one trial (/w). Prints one line per metric as
# key=value and ends with QUALITY_DONE. TASK = small|brown|green. Tools come from pinned pip/apt installs in the
# container only (nothing touches the host).
set -uo pipefail
cd /w || exit 2
apt-get update -qq >/dev/null 2>&1 && apt-get install -y -qq --no-install-recommends bats shellcheck git >/dev/null 2>&1
pip install -q --disable-pip-version-check ruff==0.14.2 lizard==1.17.31 radon==6.0.1 pyyaml==6.0.3 pytest==9.0.1 httpx==0.28.1 >/dev/null 2>&1
echo "tools=$(ruff --version) | lizard $(lizard --version) | $(shellcheck --version | sed -n 2p)"

lizard_stats() {  # <py file> → max CCN, avg CCN, functions, NLOC
  lizard --csv "$1" 2>/dev/null | awk -F, 'NR>0 {n++; c+=$2; if ($2>m) m=$2; l+=$1} END {printf "ccn_max=%d ccn_avg=%.2f functions=%d nloc=%d\n", m, (n?c/n:0), n, l}'
}

case "$TASK" in
  small)
    f=scripts/tests/alert-rules.bats
    echo "shellcheck_findings=$(shellcheck -s bats -f gcc "$f" 2>/dev/null | wc -l)"
    echo "bats_tests=$(grep -c '^@test' "$f")"
    echo "harness_lines=$(wc -l < "$f")"
    # the embedded Python block that does the parsing/guarding (between the heredoc markers)
    # the line opening the block reads `python3 - ... <<'PY' || return 1`, so match the marker anywhere on the line
    awk "/<<'PY'/{f=1; next} /^PY\$/{f=0} f" "$f" > /tmp/harness.py
    echo "embedded_py_lines=$(wc -l < /tmp/harness.py)"
    echo "ruff_findings=$(ruff check --select E,F,W,B,C90 --ignore E501 --quiet --output-format concise /tmp/harness.py 2>/dev/null | grep -c ':')"
    lizard_stats /tmp/harness.py
    # promtool for the trial's own bats suite (the container has none): the same 3.5.3 CI uses, from the toolbox copy
    cp /t/promtool /usr/local/bin/promtool 2>/dev/null
    python3 /q/mutate.py /w "$f" "bats $f >/dev/null 2>&1" | sed 's/^/mutation=/'
    ;;
  brown)
    g=scripts/check-private-lanes.py
    [ -f "$g" ] || { echo "error=no guard"; echo QUALITY_DONE; exit 0; }
    echo "guard_lines=$(wc -l < "$g")"
    echo "ruff_findings=$(ruff check --select E,F,W,B,C90 --ignore E501 --quiet --output-format concise "$g" 2>/dev/null | grep -c ':')"
    lizard_stats "$g"
    echo "radon_mi=$(radon mi -s "$g" | sed -E 's/.* - [A-F] \(([0-9.]+)\)/\1/')"
    tests=$(grep -rl "check-private-lanes" scripts/tests --include='*.bats' | tr '\n' ' ')
    echo "own_test_files=$tests"
    echo "own_bats_cases=$(cat $tests 2>/dev/null | grep -c '^@test')"
    python3 /q/mutate.py /w "$g" "bats $tests >/dev/null 2>&1" | sed 's/^/mutation=/'
    ;;
  green)
    s=nodes/mother/lab/weyland-platform/services/store-scaler
    [ -f "$s/app.py" ] || { echo "error=no app.py"; echo QUALITY_DONE; exit 0; }
    pip install -q --disable-pip-version-check -r "$s/requirements.txt" >/dev/null 2>&1 || echo "warn=requirements install failed"
    echo "app_lines=$(wc -l < "$s/app.py")"
    echo "py_files=$(find "$s" -name '*.py' -not -path '*/tests/*' -not -name 'conftest.py' | wc -l)"
    echo "ruff_findings=$(ruff check --select E,F,W,B,C90 --ignore E501 --quiet --output-format concise "$s/app.py" 2>/dev/null | grep -c ':')"
    lizard_stats "$s/app.py"
    echo "radon_mi=$(radon mi -s "$s/app.py" | sed -E 's/.* - [A-F] \(([0-9.]+)\)/\1/')"
    echo "own_test_cases=$(cd "$s" && python -m pytest -q --collect-only -p no:cacheprovider 2>/dev/null | grep -cE '::')"
    echo "dockerfile_nonroot=$(grep -cE '^USER ' "$s/Dockerfile" 2>/dev/null)"
    python3 /q/mutate.py "/w/$s" app.py "python -m pytest -q -x -p no:cacheprovider >/dev/null 2>&1" | sed 's/^/mutation=/'
    ;;
  vague)
    # the brief named no file: the checker is the largest .py the trial ADDED under scripts/ (vs the base commit)
    git config --global --add safe.directory /w
    root=$(git rev-list --max-parents=0 HEAD)
    g=$( { git diff --name-only "$root"; git ls-files --others --exclude-standard; } | grep -E '^scripts/.*\.py$' | sort -u \
         | while read -r p; do [ -f "$p" ] && printf '%s %s\n' "$(wc -l < "$p")" "$p"; done | sort -rn | head -1 | awk '{print $2}')
    [ -n "$g" ] || { echo "error=no new python checker"; echo QUALITY_DONE; exit 0; }
    echo "checker=$g"
    echo "checker_lines=$(wc -l < "$g")"
    echo "ruff_findings=$(ruff check --select E,F,W,B,C90 --ignore E501 --quiet --output-format concise "$g" 2>/dev/null | grep -c ':')"
    lizard_stats "$g"
    echo "radon_mi=$(radon mi -s "$g" | sed -E 's/.* - [A-F] \(([0-9.]+)\)/\1/')"
    base=$(basename "$g")
    tests=$(grep -rl "$base" scripts/tests --include='*.bats' | tr '\n' ' ')
    echo "own_test_files=$tests"
    echo "own_bats_cases=$(cat $tests 2>/dev/null | grep -c '^@test')"
    cp /t/promtool /usr/local/bin/promtool 2>/dev/null
    # CI runs these with bats 1.14 (bats/bats); Debian's apt bats is older and fails some trials' own suites
    export PATH="/t/bats-core/bin:$PATH"
    if [ -n "$tests" ]; then
      python3 /q/mutate.py /w "$g" "bats $tests >/dev/null 2>&1" | sed 's/^/mutation=/'
    else
      echo 'mutation={"mutants": 0, "score": null, "baseline": "no own tests"}'
    fi
    ;;
esac
echo QUALITY_DONE
