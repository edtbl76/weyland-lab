#!/usr/bin/env python3
"""sqlite_backup.py — nightly backup of an app whose whole state is ONE live SQLite file (docs/dr.md).

    sqlite_backup.py --db FILE --require TABLE [--require TABLE ...] [--count TABLE ...] [--archive DIR ...]
                     --keep N <data-dir> <backup-root>

Used by (each a CronJob running a byte-identical embedded copy — scripts/embed-sqlite-backup.sh):
  open-webui-backup  --db webui.db --require user --count chat --archive vector_db --archive uploads
  woodpecker-backup  --db woodpecker.sqlite --require users --require pipelines

Writes <backup-root>/<UTC timestamp>/ with:
  <FILE>            a CONSISTENT snapshot via SQLite's online backup API (a file copy of a live WAL db is not one)
  <DIR>.tar.gz      each --archive directory (skipped if absent)
  manifest.json     written LAST: integrity, row counts, files — a backup dir without it is not a backup

FAIL CLOSED (exit 2, nothing left that looks like a backup): a missing source db, a copy whose integrity_check is not
"ok", a --require table that is missing or EMPTY (the wrong file, an empty one, or a schema change — never the real
state), or no --require at all (a check that checks nothing). The run writes into `.inprogress-<ts>` and renames it only
once complete; rotation keeps the newest --keep complete backups and removes interrupted runs.
Restores: docs/runbooks/open-webui.md, docs/runbooks/woodpecker.md.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import tarfile
import time

IN_PROGRESS = ".inprogress-"
MANIFEST = "manifest.json"


class BackupInvalid(Exception):
    pass


class UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """argparse that RAISES on a bad command line instead of calling sys.exit(), so main() reports it as exit 2."""

    def error(self, message):
        raise UsageError(message)


def snapshot(src_db: str, dst_db: str) -> None:
    """Copy a live (WAL) SQLite db consistently, including WAL-only commits."""
    if not os.path.exists(src_db):
        raise BackupInvalid(f"source database {src_db} does not exist")
    src = sqlite3.connect(src_db)
    dst = sqlite3.connect(dst_db)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def verify(db: str, required: list, counted: list) -> dict:
    """Prove the copy is the app's real state: integrity ok and every required table non-empty."""
    c = sqlite3.connect(db)
    try:
        integrity = c.execute("pragma integrity_check").fetchone()[0]
        counts = {}
        for table in required + counted:
            try:
                counts[table] = c.execute(f'select count(*) from "{table}"').fetchone()[0]  # noqa: S608 — table names come from the CronJob's own args
            except sqlite3.DatabaseError as exc:
                raise BackupInvalid(f"the copy has no table {table}: {exc}") from exc
    finally:
        c.close()
    if integrity != "ok":
        raise BackupInvalid(f"integrity_check on the copy returned {integrity!r}")
    for table in required:
        if counts[table] < 1:
            raise BackupInvalid(f"required table {table} is empty — the wrong or an empty database, not the app's state")
    return {"integrity": integrity, "counts": counts}


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


def run(args) -> str:
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    os.makedirs(args.backup_root, exist_ok=True)
    work = os.path.join(args.backup_root, IN_PROGRESS + ts)
    os.makedirs(work)
    try:
        copy = os.path.join(work, args.db)
        snapshot(os.path.join(args.data_dir, args.db), copy)
        stats = verify(copy, args.require, args.count)
        for name in args.archive:
            archive(args.data_dir, name, work)
        files = sorted(os.listdir(work))
        manifest = {"timestamp": ts, "db": args.db, **stats, "files": files,
                    "bytes": {f: os.path.getsize(os.path.join(work, f)) for f in files}}
        with open(os.path.join(work, MANIFEST), "w") as f:
            json.dump(manifest, f, indent=1)
        final = os.path.join(args.backup_root, ts)
        os.rename(work, final)
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
    rotate(args.backup_root, args.keep)
    return final


def main(argv: list) -> int:
    p = _Parser(prog="sqlite_backup.py", description=__doc__.split("\n", 1)[0])
    p.add_argument("--db", required=True)
    p.add_argument("--require", action="append", default=[])
    p.add_argument("--count", action="append", default=[])
    p.add_argument("--archive", action="append", default=[])
    p.add_argument("--keep", type=int, required=True)
    p.add_argument("data_dir")
    p.add_argument("backup_root")
    try:
        args = p.parse_args(argv)
    except UsageError as exc:
        print(f"sqlite-backup FAILED: {exc}\n{p.format_usage().strip()}", file=sys.stderr)
        return 2
    if not args.require:
        print("sqlite-backup FAILED: no --require table — a check that checks nothing is not a backup", file=sys.stderr)
        return 2
    try:
        final = run(args)
    except (BackupInvalid, OSError, sqlite3.Error) as exc:
        print(f"sqlite-backup FAILED ({args.db}): {exc}", file=sys.stderr)
        return 2
    m = json.load(open(os.path.join(final, MANIFEST)))
    print(f"sqlite-backup OK ({args.db}): {final} — counts={m['counts']} files={m['files']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
