"""A complete copy of the database as one file, and putting it back.

    python -m assistant.backup export munshi-backup.json.gz
    python -m assistant.backup restore munshi-backup.json.gz --replace-everything

The file holds every table (businesses, calls, contacts, settings, sign-ins). Keys for outside services stay encrypted inside it, so it can only be
restored with the same LAB_SECRET_KEY. Treat the file like the database itself: it contains callers' numbers and conversations.
Managed Postgres backups (Supabase) are still the first line of defence; this is the copy you can read, move and test a restore from.
"""
from __future__ import annotations

import gzip
import json
import sys
from datetime import date, datetime

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.sqltypes import Boolean, DateTime

from lab.models import Base, utcnow

FORMAT = 1


def _tables():
    return list(Base.metadata.sorted_tables)  # parents before children


def dump(session: Session) -> dict:
    tables = {}
    for t in _tables():
        rows = []
        for r in session.execute(select(t)).mappings():
            rows.append({k: (v.isoformat() if isinstance(v, (datetime, date)) else v) for k, v in r.items()})
        tables[t.name] = rows
    return {"format": FORMAT, "made_at": utcnow().isoformat(), "counts": {k: len(v) for k, v in tables.items()}, "tables": tables}


def to_bytes(session: Session) -> bytes:
    return gzip.compress(json.dumps(dump(session), ensure_ascii=False, default=str).encode("utf-8"))


def _revive(table, row: dict) -> dict:
    out = {}
    for k, v in row.items():
        col = table.c[k]
        if v is not None and isinstance(col.type, DateTime) and isinstance(v, str):
            v = datetime.fromisoformat(v)
        elif v is not None and isinstance(col.type, Boolean):
            v = bool(v)
        out[k] = v
    return out


def restore(session: Session, data: dict, *, replace: bool = False) -> dict:
    """Load a dump. With replace=True everything now in the database is removed first; without it the tables must be empty."""
    if data.get("format") != FORMAT:
        raise ValueError("This is not a Munshi backup file, or it is from a newer version.")
    tables = _tables()
    if replace:
        for t in reversed(tables):
            session.execute(delete(t))
    else:
        busy = [t.name for t in tables if t.name in data["tables"] and session.execute(select(t).limit(1)).first() is not None]
        if busy:
            raise ValueError("The database is not empty (" + ", ".join(busy[:4]) + "). Restore into an empty database, or pass --replace-everything.")
    done = {}
    for t in tables:
        rows = data["tables"].get(t.name) or []
        known = set(t.c.keys())
        for chunk_start in range(0, len(rows), 500):
            session.execute(insert(t), [_revive(t, {k: v for k, v in r.items() if k in known}) for r in rows[chunk_start:chunk_start + 500]])
        done[t.name] = len(rows)
    return done


def _main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[1] not in ("export", "restore"):
        print(__doc__)
        return 2
    from lab import db
    from lab.config import load_settings

    db.init_db(load_settings())
    path = argv[2]
    with db.session_scope() as s:
        if argv[1] == "export":
            blob = to_bytes(s)
            open(path, "wb").write(blob)
            print(f"wrote {path} ({len(blob) // 1024} KB)")
        else:
            data = json.loads(gzip.decompress(open(path, "rb").read()))
            print("restored:", restore(s, data, replace="--replace-everything" in argv))
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
