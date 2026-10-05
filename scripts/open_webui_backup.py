#!/usr/bin/env python3
"""open_webui_backup.py — nightly backup of Open WebUI's state (2026-10-04, DoD pillar 9; docs/dr.md).

    open_webui_backup.py <data-dir> <backup-root> <keep>

Open WebUI keeps its users, chats, settings (incl. the shared-memory MCP tool-server connection) and model presets in
ONE SQLite file, `webui.db`, in WAL mode, on a RWO PVC — and nothing backed it up. This writes
<backup-root>/<UTC timestamp>/ with:
  webui.db           a CONSISTENT snapshot via SQLite's online backup API (a file copy of a live WAL db is not one)
  vector_db.tar.gz   the local RAG index (regenerable from uploads; archived so a restore is complete)
  uploads.tar.gz     uploaded files
  manifest.json      written LAST: integrity, counts, files — a backup dir without it is not a backup
`cache/` (~0.9 GB of downloaded model files) is skipped: Open WebUI re-downloads it.

FAIL CLOSED (exit 2, nothing left that looks like a backup): a missing source db, a copy whose integrity_check is not
"ok", or a copy with no users (an Open WebUI with zero accounts is the wrong file or an empty one, never the real
state). The run writes into `.inprogress-<ts>` and renames it only once complete; rotation keeps the newest <keep>
complete backups and removes interrupted runs.

Run by the `open-webui-backup` CronJob (k8s/open-webui/backup.yaml) from a byte-identical copy embedded by
scripts/embed-open-webui-backup.sh. Restore: docs/runbooks/open-webui.md.
"""
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import time

IN_PROGRESS = ".inprogress-"


class BackupInvalid(Exception):
    pass


def snapshot(src_db: str, dst_db: str) -> None:
    """Copy a live (WAL) SQLite db consistently, including WAL-only commits."""
    if not os.path.exists(src_db):
        raise BackupInvalid(f"source database {src_db} does not exist (webui.db missing)")
    src = sqlite3.connect(src_db)
    dst = sqlite3.connect(dst_db)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def verify(db: str) -> dict:
    """Prove the copy is a real Open WebUI state: integrity ok and at least one user."""
    c = sqlite3.connect(db)
    try:
        integrity = c.execute("pragma integrity_check").fetchone()[0]
        users = c.execute("select count(*) from user").fetchone()[0]
        chats = c.execute("select count(*) from chat").fetchone()[0]
        tool_servers = c.execute("select count(*) from config where key = 'tool_server.connections'").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise BackupInvalid(f"the copy is not a readable Open WebUI database: {exc}") from exc
    finally:
        c.close()
    if integrity != "ok":
        raise BackupInvalid(f"integrity_check on the copy returned {integrity!r}")
    if users < 1:
        raise BackupInvalid("the copy has no users — the wrong or an empty database, not Open WebUI's state")
    return {"integrity": integrity, "users": users, "chats": chats, "tool_servers_configured": tool_servers > 0}


def archive(src_dir: str, name: str, dst_dir: str) -> str | None:
    """tar.gz <src_dir>/<name> into <dst_dir>/<name>.tar.gz; None if the directory does not exist."""
    path = os.path.join(src_dir, name)
    if not os.path.isdir(path):
        return None
    out = os.path.join(dst_dir, f"{name}.tar.gz")
    with tarfile.open(out, "w:gz") as t:
        t.add(path, arcname=name)
    return out


def rotate(root: str, keep: int) -> list:
    """Remove interrupted runs and all but the newest <keep> complete backups. Returns what was removed."""
    removed = []
    entries = sorted(os.listdir(root))
    for d in entries:
        if d.startswith(IN_PROGRESS):
            shutil.rmtree(os.path.join(root, d))
            removed.append(d)
    complete = [d for d in entries if not d.startswith(".")]
    for d in complete[:-keep] if keep > 0 else []:
        shutil.rmtree(os.path.join(root, d))
        removed.append(d)
    return removed


def run(data_dir: str, root: str, keep: int) -> str:
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    os.makedirs(root, exist_ok=True)
    work = os.path.join(root, IN_PROGRESS + ts)
    os.makedirs(work)
    try:
        snapshot(os.path.join(data_dir, "webui.db"), os.path.join(work, "webui.db"))
        stats = verify(os.path.join(work, "webui.db"))
        for name in ("vector_db", "uploads"):
            archive(data_dir, name, work)
        files = sorted(os.listdir(work))
        manifest = {"timestamp": ts, **stats, "files": files,
                    "bytes": {f: os.path.getsize(os.path.join(work, f)) for f in files}}
        with open(os.path.join(work, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=1)
        final = os.path.join(root, ts)
        os.rename(work, final)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    rotate(root, keep)
    return final


def main(argv: list) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    data_dir, root, keep = argv[0], argv[1], int(argv[2])
    try:
        final = run(data_dir, root, keep)
    except (BackupInvalid, OSError, sqlite3.Error) as exc:
        print(f"open-webui-backup FAILED: {exc}", file=sys.stderr)
        return 2
    m = json.load(open(os.path.join(final, "manifest.json")))
    print(f"open-webui-backup OK: {final} — users={m['users']} chats={m['chats']} "
          f"tool_servers_configured={m['tool_servers_configured']} files={m['files']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
