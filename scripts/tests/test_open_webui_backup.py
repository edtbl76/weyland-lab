"""Tests for open_webui_backup.py — the nightly Open WebUI backup (2026-10-04, DoD pillar 9).

Open WebUI keeps its users, chats, settings (incl. the shared-memory tool-server connection) and model presets in one
SQLite file in WAL mode, `webui.db`, on a RWO PVC — and it had NO backup. These pin down the decisions: the copy is a
consistent snapshot of a LIVE database (SQLite's backup API, never a file copy of a WAL db), a backup that proves
nothing (no users, a corrupt copy, a missing source) fails CLOSED and leaves nothing that looks like a backup behind,
the manifest is written last so a complete backup is self-evident, and rotation keeps the newest 7 and clears
interrupted runs.
"""
import json
import os
import sqlite3
import sys
import tarfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # scripts/ on path

import open_webui_backup as ob


def _live_db(data_dir, users=1, chats=2):
    """A WAL-mode webui.db shaped like Open WebUI's (the tables the backup reads), left OPEN like the live app."""
    os.makedirs(data_dir, exist_ok=True)
    c = sqlite3.connect(os.path.join(data_dir, "webui.db"))
    c.execute("pragma journal_mode=wal")
    c.execute("create table user (id text)")
    c.execute("create table chat (id text)")
    c.execute("create table config (key text, value text)")
    c.executemany("insert into user values (?)", [(f"u{i}",) for i in range(users)])
    c.executemany("insert into chat values (?)", [(f"c{i}",) for i in range(chats)])
    c.execute("insert into config values ('tool_server.connections', '[]')")
    c.commit()
    os.makedirs(os.path.join(data_dir, "vector_db"), exist_ok=True)
    with open(os.path.join(data_dir, "vector_db", "chroma.sqlite3"), "w") as f:
        f.write("index")
    os.makedirs(os.path.join(data_dir, "uploads"), exist_ok=True)
    return c          # caller keeps it open: the WAL is not checkpointed, as on the live PVC


def _backups(root):
    return sorted(d for d in os.listdir(root) if not d.startswith("."))


def test_a_live_wal_database_is_snapshotted_consistently(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    live = _live_db(str(data), users=2, chats=3)
    live.execute("insert into chat values ('in-wal')")    # committed to the WAL, not yet in webui.db
    live.commit()
    assert ob.main([str(data), str(root), "7"]) == 0
    (b,) = _backups(root)
    copy = sqlite3.connect(os.path.join(root, b, "webui.db"))
    assert copy.execute("select count(*) from chat").fetchone()[0] == 4      # the WAL-only row is in the copy
    m = json.load(open(os.path.join(root, b, "manifest.json")))
    assert m["integrity"] == "ok" and m["users"] == 2 and m["chats"] == 4 and m["tool_servers_configured"] is True


def test_vector_db_and_uploads_are_archived(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    _live_db(str(data))
    ob.main([str(data), str(root), "7"])
    (b,) = _backups(root)
    with tarfile.open(os.path.join(root, b, "vector_db.tar.gz")) as t:
        assert "vector_db/chroma.sqlite3" in t.getnames()
    assert os.path.exists(os.path.join(root, b, "uploads.tar.gz"))


def test_a_database_with_no_users_fails_closed_and_leaves_nothing(tmp_path, capsys):
    data, root = tmp_path / "data", tmp_path / "backup"
    _live_db(str(data), users=0)
    assert ob.main([str(data), str(root), "7"]) == 2
    assert "no users" in capsys.readouterr().err
    assert os.listdir(root) == []                          # no backup dir and no half-written temp dir


def test_a_missing_source_database_fails_closed(tmp_path, capsys):
    (tmp_path / "data").mkdir()
    assert ob.main([str(tmp_path / "data"), str(tmp_path / "backup"), "7"]) == 2
    assert "webui.db" in capsys.readouterr().err


def test_rotation_keeps_the_newest_and_clears_interrupted_runs(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    _live_db(str(data))
    root.mkdir()
    for i in range(9):
        (root / f"20260901T00000{i}Z").mkdir()
    (root / ".inprogress-20260901T000000Z").mkdir()          # a run killed mid-write
    assert ob.main([str(data), str(root), "7"]) == 0
    kept = _backups(root)
    assert len(kept) == 7 and kept[-1] > "20260901T000008Z"  # the new one is kept, the oldest removed
    assert not any(d.startswith(".inprogress") for d in os.listdir(root))


def test_the_manifest_is_written_last(tmp_path):
    data, root = tmp_path / "data", tmp_path / "backup"
    _live_db(str(data))
    ob.main([str(data), str(root), "7"])
    (b,) = _backups(root)
    names = os.listdir(os.path.join(root, b))
    assert "manifest.json" in names
    m = json.load(open(os.path.join(root, b, "manifest.json")))
    assert set(m["files"]) == set(names) - {"manifest.json"}  # it lists every file already written
