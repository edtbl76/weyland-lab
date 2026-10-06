"""Tests for sqlite_backup.py — the nightly backup of a live SQLite app store (Open WebUI 2026-10-04; Woodpecker 2026-10-05).

Two apps keep their whole state in ONE SQLite file in WAL mode on a RWO PVC: Open WebUI (`webui.db` — users, chats,
settings, the shared-memory tool connection) and Woodpecker (`woodpecker.sqlite` — users, repos, secrets, the nightly
cron, pipeline history). Neither had a backup. One script serves both, configured per app by which tables must be
non-empty. These pin down the decisions: the copy is a consistent snapshot of a LIVE database (SQLite's backup API,
never a file copy of a WAL db), a backup that proves nothing (a required table empty or missing, a corrupt copy, a
missing source) fails CLOSED and leaves nothing that looks like a backup behind, the manifest is written last, and
rotation keeps the newest N and clears interrupted runs.
"""
import json
import os
import sqlite3
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import sqlite_backup as sb

OPEN_WEBUI = ["--db", "webui.db", "--require", "user", "--count", "chat", "--archive", "vector_db", "--archive", "uploads"]
WOODPECKER = ["--db", "woodpecker.sqlite", "--require", "users", "--require", "pipelines"]


def _live_db(data_dir, name, rows):
    """A WAL-mode db with {table: n_rows}, left OPEN like the live app."""
    os.makedirs(data_dir, exist_ok=True)
    c = sqlite3.connect(os.path.join(data_dir, name))
    c.execute("pragma journal_mode=wal")
    for table, n in rows.items():
        c.execute(f"create table {table} (id text)")
        c.executemany(f"insert into {table} values (?)", [(f"{table}{i}",) for i in range(n)])
    c.commit()
    return c


def _owui(data_dir, users=1, chats=2):
    c = _live_db(data_dir, "webui.db", {"user": users, "chat": chats})
    for d, f in (("vector_db", "chroma.sqlite3"), ("uploads", None)):
        os.makedirs(os.path.join(data_dir, d), exist_ok=True)
        if f:
            with open(os.path.join(data_dir, d, f), "w") as fh:
                fh.write("index")
    return c


def _backups(root):
    return sorted(d for d in os.listdir(root) if not d.startswith("."))


def _run(args, data, root, keep="7"):
    return sb.main(args + ["--keep", keep, str(data), str(root)])


def test_a_live_wal_database_is_snapshotted_consistently(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    live = _owui(str(data), users=2, chats=3)
    live.execute("insert into chat values ('in-wal')")    # committed to the WAL, not yet in webui.db
    live.commit()
    assert _run(OPEN_WEBUI, data, root) == 0
    (b,) = _backups(root)
    copy = sqlite3.connect(os.path.join(root, b, "webui.db"))
    assert copy.execute("select count(*) from chat").fetchone()[0] == 4     # the WAL-only row is in the copy
    m = json.load(open(os.path.join(root, b, "manifest.json")))
    assert m["integrity"] == "ok" and m["counts"] == {"user": 2, "chat": 4} and m["db"] == "webui.db"


def test_open_webui_archives_its_directories(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    _owui(str(data))
    _run(OPEN_WEBUI, data, root)
    (b,) = _backups(root)
    with tarfile.open(os.path.join(root, b, "vector_db.tar.gz")) as t:
        assert "vector_db/chroma.sqlite3" in t.getnames()
    assert os.path.exists(os.path.join(root, b, "uploads.tar.gz"))


def test_woodpecker_is_backed_up_with_its_own_required_tables(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    _live_db(str(data), "woodpecker.sqlite", {"users": 1, "pipelines": 260, "secrets": 4})
    assert _run(WOODPECKER, data, root) == 0
    (b,) = _backups(root)
    m = json.load(open(os.path.join(root, b, "manifest.json")))
    assert m["counts"] == {"users": 1, "pipelines": 260} and m["files"] == ["woodpecker.sqlite"]


def test_an_empty_required_table_fails_closed_and_leaves_nothing(tmp_path, capsys):
    data, root = tmp_path / "data", tmp_path / "backup"
    _owui(str(data), users=0)
    assert _run(OPEN_WEBUI, data, root) == 2
    assert "required table user is empty" in capsys.readouterr().err
    assert os.listdir(root) == []                          # no backup dir and no half-written temp dir


def test_a_missing_required_table_fails_closed(tmp_path, capsys):
    data, root = tmp_path / "data", tmp_path / "backup"
    _live_db(str(data), "woodpecker.sqlite", {"users": 1})  # no pipelines table — the wrong file, or a schema change
    assert _run(WOODPECKER, data, root) == 2
    assert "pipelines" in capsys.readouterr().err


def test_a_missing_source_database_fails_closed(tmp_path, capsys):
    (tmp_path / "data").mkdir()
    assert _run(OPEN_WEBUI, tmp_path / "data", tmp_path / "backup") == 2
    assert "webui.db" in capsys.readouterr().err


def test_no_required_table_is_a_usage_error_not_a_pass(tmp_path, capsys):
    data, root = tmp_path / "data", tmp_path / "backup"
    _owui(str(data))
    assert sb.main(["--db", "webui.db", "--keep", "7", str(data), str(root)]) == 2   # a check that checks nothing
    assert "--require" in capsys.readouterr().err


def test_rotation_keeps_the_newest_and_clears_interrupted_runs(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    _owui(str(data))
    root.mkdir()
    for i in range(9):
        (root / f"20260901T00000{i}Z").mkdir()
    (root / ".inprogress-20260901T000000Z").mkdir()          # a run killed mid-write
    assert _run(OPEN_WEBUI, data, root) == 0
    kept = _backups(root)
    assert len(kept) == 7 and kept[-1] > "20260901T000008Z"  # the new one is kept, the oldest removed
    assert not any(d.startswith(".inprogress") for d in os.listdir(root))


def test_the_manifest_is_written_last(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    _owui(str(data))
    _run(OPEN_WEBUI, data, root)
    (b,) = _backups(root)
    names = os.listdir(os.path.join(root, b))
    m = json.load(open(os.path.join(root, b, "manifest.json")))
    assert set(m["files"]) == set(names) - {"manifest.json"}  # it lists every file already written


def test_a_bad_command_line_is_exit_2_with_the_reason(tmp_path, capsys):
    # argparse would sys.exit() itself; the script reports a usage error as its own exit 2 (fail closed) instead.
    assert sb.main(["--require", "user", "--keep", "7", str(tmp_path), str(tmp_path / "b")]) == 2   # no --db
    assert "--db" in capsys.readouterr().err
