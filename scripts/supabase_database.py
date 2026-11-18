"""Check the Supabase connection or copy local forecast snapshots into Supabase."""

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from forecast_store import DB_PATH
from supabase_store import StoreError, configured_store


def migrate_local(store, path):
    # Read-only: the original database and its IDs remain untouched.
    path = Path(path).resolve()
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        count = 0
        for row in db.execute("SELECT * FROM forecast_runs ORDER BY id"):
            record = dict(row)
            record.pop("id")
            store.save(record)
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "migrate-local"])
    parser.add_argument("--database", type=Path, default=DB_PATH)
    args = parser.parse_args()
    try:
        store = configured_store()
        if store is None:
            raise StoreError("Configure Supabase in .streamlit/secrets.toml or environment variables first.")
        store.request("GET", {"select": "id", "limit": 1})
        if args.command == "migrate-local":
            count = migrate_local(store, args.database)
            print(f"Copied {count} local snapshots to Supabase. Duplicates were skipped; local data is unchanged.")
        else:
            print("Connected to Supabase. Forecast history table is readable.")
    except (StoreError, sqlite3.Error, OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
