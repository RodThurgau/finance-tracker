import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from database import DB_PATH

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
KEEP_RECENT = 20
KEEP_DAILY_DAYS = 30

_SNAPSHOT_RE = re.compile(r"^finance-(\d{8}-\d{6})\.db$")


class BackupError(Exception):
    """Raised when the pre-migration snapshot cannot be created."""


def _snapshot_timestamp(path: Path) -> datetime | None:
    match = _SNAPSHOT_RE.match(path.name)
    if match is None:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d-%H%M%S")


def create_backup() -> Path | None:
    """Snapshot data/finance.db into backups/ via SQLite's VACUUM INTO.

    Returns the snapshot path, or None if there is no database yet to back up
    (e.g. first-ever startup). Raises BackupError if a database exists but the
    snapshot could not be written.
    """
    if not DB_PATH.exists():
        return None

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_path = BACKUP_DIR / f"finance-{timestamp}.db"

    try:
        source = sqlite3.connect(DB_PATH)
        try:
            source.execute("VACUUM INTO ?", (str(snapshot_path),))
        finally:
            source.close()
    except sqlite3.Error as exc:
        raise BackupError(f"Failed to back up {DB_PATH} to {snapshot_path}: {exc}") from exc

    return snapshot_path


def prune_backups() -> list[Path]:
    """Enforce retention: most recent KEEP_RECENT snapshots, plus the first
    snapshot of each day for the last KEEP_DAILY_DAYS days. Deletes the rest.

    Returns the list of deleted paths.
    """
    snapshots = sorted(
        (p for p in BACKUP_DIR.glob("finance-*.db") if _snapshot_timestamp(p) is not None),
        key=_snapshot_timestamp,
        reverse=True,
    )

    keep: set[Path] = set(snapshots[:KEEP_RECENT])

    cutoff = datetime.now() - timedelta(days=KEEP_DAILY_DAYS)
    first_of_day: dict[str, Path] = {}
    for path in sorted(snapshots, key=_snapshot_timestamp):
        ts = _snapshot_timestamp(path)
        if ts is None or ts < cutoff:
            continue
        day_key = ts.strftime("%Y%m%d")
        first_of_day.setdefault(day_key, path)
    keep.update(first_of_day.values())

    deleted = []
    for path in snapshots:
        if path not in keep:
            path.unlink()
            deleted.append(path)

    return deleted


def run_backup() -> Path | None:
    """Create a snapshot, then prune old ones. Called on every startup, before migrations."""
    snapshot_path = create_backup()
    prune_backups()
    return snapshot_path
