"""lab_commands: the runbook command roster behind `lab-commands` and `lab-ask` (B187 follow-on).

The runbooks are the ONLY source of the lab's commands (AGENTS.md: one canonical command per task, in a runbook), so
the roster is regenerated from them on every call and never stored. These tests pin the three ways runbooks write a
command (fenced block under a host label, `[host] cmd` inside a fence, inline backticks in prose) and the fail-closed
contract of the CLI.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

import lab_commands as lc

CLI = Path(__file__).resolve().parents[1] / "lab-commands.py"

RUNBOOK = textwrap.dedent("""\
    # Woodpecker CI

    ## Trigger a run

    - **Trigger:** manual (`woodpecker-cli pipeline create edtbl76/weyland-lab --branch main`). No LAN webhooks.

    [rogueone]
    ```bash
    set -a && . scripts/.env && set +a
    woodpecker-cli pipeline ps edtbl76/weyland-lab 603
    ```

    ### Logs

    ```
    [mother] kubectl -n woodpecker logs deploy/woodpecker-server --tail=50
    ```

    ## Config

    ```yaml
    steps:
      - name: build
    ```

    ```
    pipeline 603: success
    ```

    ```mermaid
    sequenceDiagram
        A->>B: kubectl apply
    ```
    """)


def _entries():
    return lc.extract(RUNBOOK, "docs/runbooks/woodpecker.md")


def _find(entries, needle):
    hits = [e for e in entries if needle in e.command]
    assert len(hits) == 1, (needle, [e.command for e in entries])
    return hits[0]


def test_inline_command_in_prose_is_captured():
    # The canonical CI trigger lives in a bullet as inline code; a fence-only parser misses it.
    e = _find(_entries(), "pipeline create")
    assert e.command == "woodpecker-cli pipeline create edtbl76/weyland-lab --branch main"
    assert e.section == "Trigger a run"
    assert e.host == ""


def test_fence_under_a_host_label_carries_the_host_and_whole_block():
    e = _find(_entries(), "pipeline ps")
    assert e.host == "rogueone"
    assert e.command.splitlines() == [
        "set -a && . scripts/.env && set +a",
        "woodpecker-cli pipeline ps edtbl76/weyland-lab 603",
    ]


def test_host_prefix_inside_a_fence_is_split_off():
    e = _find(_entries(), "kubectl -n woodpecker logs")
    assert e.host == "mother"
    assert e.command == "kubectl -n woodpecker logs deploy/woodpecker-server --tail=50"
    assert e.section == "Trigger a run > Logs"


def test_config_output_and_diagram_blocks_are_not_commands():
    commands = " ".join(e.command for e in _entries())
    assert "name: build" not in commands
    assert "pipeline 603: success" not in commands
    assert "A->>B" not in commands
    assert len(_entries()) == 3


def test_entry_links_back_to_its_runbook_section():
    e = _find(_entries(), "kubectl -n woodpecker logs")
    assert e.source == "docs/runbooks/woodpecker.md#logs"
    assert e.title == "Woodpecker CI"


def test_render_shows_source_host_and_command():
    text = lc.render(_entries())
    assert "## Woodpecker CI > Trigger a run > Logs (docs/runbooks/woodpecker.md#logs)" in text
    assert "[mother] kubectl -n woodpecker logs deploy/woodpecker-server --tail=50" in text
    assert "[any] woodpecker-cli pipeline create edtbl76/weyland-lab --branch main" in text


def test_grep_needs_every_word_case_insensitively():
    entries = _entries()
    assert [e.host for e in lc.grep(entries, ["WOODPECKER", "logs"])] == ["mother"]
    assert lc.grep(entries, ["woodpecker", "nonexistent"]) == []


def test_prompt_carries_the_question_the_index_and_the_not_found_rule():
    p = lc.prompt("restart the CI server", lc.render(_entries()))
    assert "restart the CI server" in p
    assert "pipeline create" in p
    assert "not in the index" in p.lower()


def _cli(*args, root):
    return subprocess.run([sys.executable, str(CLI), "--root", str(root), *args], capture_output=True, text=True)


def test_cli_fails_closed_when_there_are_no_runbooks(tmp_path):
    r = _cli(root=tmp_path)
    assert r.returncode == 2
    assert "no runbooks" in r.stderr


def test_cli_fails_closed_when_runbooks_hold_no_commands(tmp_path):
    (tmp_path / "docs" / "runbooks").mkdir(parents=True)
    (tmp_path / "docs" / "runbooks" / "empty.md").write_text("# Empty\n\nJust prose.\n")
    r = _cli(root=tmp_path)
    assert r.returncode == 2
    assert "no commands" in r.stderr


def test_cli_also_reads_the_dr_catalog(tmp_path):
    # Restore commands live in docs/dr.md, not in a runbook; without it lab-ask cannot answer "how do I restore X".
    (tmp_path / "docs" / "runbooks").mkdir(parents=True)
    (tmp_path / "docs" / "runbooks" / "woodpecker.md").write_text(RUNBOOK)
    (tmp_path / "docs" / "dr.md").write_text("# Disaster recovery\n\n## Bifrost\n\n[mother]\n```bash\n"
                                             "bash scripts/restore-bifrost.sh 20261022T201105Z\n```\n")
    r = _cli("--grep", "restore-bifrost", root=tmp_path)
    assert r.returncode == 0
    assert "(docs/dr.md#bifrost)" in r.stdout
    assert "[mother] bash scripts/restore-bifrost.sh 20261022T201105Z" in r.stdout


def test_cli_grep_with_no_match_exits_1(tmp_path):
    (tmp_path / "docs" / "runbooks").mkdir(parents=True)
    (tmp_path / "docs" / "runbooks" / "woodpecker.md").write_text(RUNBOOK)
    ok = _cli("--grep", "logs", root=tmp_path)
    assert ok.returncode == 0 and "kubectl -n woodpecker logs" in ok.stdout
    miss = _cli("--grep", "zzz-nothing", root=tmp_path)
    assert miss.returncode == 1
    assert "no command matches" in miss.stderr
