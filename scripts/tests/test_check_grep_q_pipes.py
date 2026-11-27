"""B271: scripts/check-grep-q-pipes.py — no `producer | grep -q` in shell that sets pipefail.

The race: grep -q exits at its first match, the producer still writing dies of SIGPIPE, and pipefail fails the
pipeline although the match was found (the dagster-watchdog-budgets CI flake, B211/#399/#746). These pin what the guard
flags and, as importantly, what it must NOT flag: a false positive trains people to ignore it.
"""
import importlib.util
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUARD = ROOT / "scripts" / "check-grep-q-pipes.py"
_spec = importlib.util.spec_from_file_location("check_grep_q_pipes", GUARD)
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

PIPEFAIL = "#!/usr/bin/env bash\nset -euo pipefail\n"


@pytest.mark.parametrize("line", [
    'printf "%s" "$out" | grep -q "x"',
    'cut -f1 <<<"$s" | grep -qx "$job"',
    'kubectl get pods -o name | grep -Fxq -- "$p"',
    'echo "$x" | grep -E -q "a|b"',
    'echo "$x" | grep --quiet y',
    'if ! printf "%s" "$v" | grep -qiE "bad"; then exit 1; fi',
    'a | grep -q y && b',
])
def test_a_pipe_into_grep_q_is_flagged(line):
    assert g.offending(line)


@pytest.mark.parametrize("line", [
    'grep -q "x" <<<"$out"',                       # here-string: grep reads all of its input
    'grep -q x file.txt',                          # a file, no pipe
    'cmd || grep -q y file',                       # || is not a pipe
    'echo "$x" | grep -c y',                       # -c reads everything
    'echo "$x" | grep -l y',
    'echo "$x" | grep "-quiet-looking-pattern"',   # a pattern, not an option
    'echo "$x" | grep -e -q',                      # -e takes the next word as the pattern
    '# printf x | grep -q y   (a comment)',
    'awk -F"\\t" -v j="$job" \'$1 == j {found = 1} END {exit !found}\' <<<"$s"',
])
def test_safe_forms_are_not_flagged(line):
    assert not g.offending(line)


def test_only_files_that_set_pipefail_are_checked(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "a.sh").write_text(PIPEFAIL + 'echo x | grep -q x\n')
    (tmp_path / "scripts" / "b.sh").write_text('#!/bin/sh\necho x | grep -q x\n')   # no pipefail: not this race
    findings, scanned = g.scan(tmp_path)
    assert [(f.split(":")[0], f.split(":")[1]) for f in findings] == [("scripts/a.sh", "3")]
    assert scanned == 1          # only the file that sets pipefail is checked


def test_shell_embedded_in_yaml_is_checked(tmp_path):
    (tmp_path / "nodes" / "k8s").mkdir(parents=True)
    (tmp_path / "nodes" / "k8s" / "job.yaml").write_text(
        "kind: CronJob\nspec:\n  args:\n    - |\n      set -eu -o pipefail\n      zcat f | tail -n 3 | grep -q 'done'\n")
    findings, _ = g.scan(tmp_path)
    assert [f.split(":")[:2] for f in findings] == [["nodes/k8s/job.yaml", "6"]]


def test_the_cli_names_each_finding_and_fails(tmp_path):
    (tmp_path / "eval").mkdir()
    (tmp_path / "eval" / "t.sh").write_text(PIPEFAIL + 'out=$(x)\nprintf "%s" "$out" | grep -q DONE && exit 0\n')
    r = subprocess.run([sys.executable, str(GUARD), "--root", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 1
    assert "eval/t.sh:4" in r.stdout and "<<<" in r.stdout          # names the site and the fix


def test_a_clean_tree_passes_and_says_how_much_it_checked(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "a.sh").write_text(PIPEFAIL + 'grep -q x <<<"$y"\n')
    r = subprocess.run([sys.executable, str(GUARD), "--root", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0 and "1 file" in r.stdout


def test_checking_nothing_is_exit_2_never_a_pass(tmp_path):
    r = subprocess.run([sys.executable, str(GUARD), "--root", str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 2
