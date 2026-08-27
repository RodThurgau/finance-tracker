"""Ad-hoc read-only SQL, for questions the UI has no screen for.

This is the one place in the app that runs SQL the ORM did not build. That is
the entire point of the feature — the tradeoff is deliberate, and CLAUDE.md
records it as an exception to "never use raw SQL strings in application code"
rather than leaving it implied. Nothing else may follow this example: every
statement here comes from the user typing it, none of it is app logic.

Three independent things keep a typo from costing a month of categorization:

1. **The statement is parsed before it runs.** It must be a single statement
   and it must start with a reading keyword, and the check is done against a
   copy with string literals and comments blanked out — so a description
   containing the word "delete" is not mistaken for a `DELETE`.
2. **The connection is opened `mode=ro`.** Even if the parser were fooled,
   SQLite itself refuses the write. See `readonly_engine` in `database.py`.
3. **Every query runs under a deadline**, enforced by SQLite's progress
   handler, so a cartesian product cannot wedge the server.

Layer 1 without layer 2 would be a parser arms race. Layer 2 without layer 1
would report SQLite's own errors for statements this app never meant to
accept. Both are cheap; neither is load-bearing alone.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Connection

# A statement has to begin with one of these. `WITH` is here because a CTE is
# an ordinary way to write a report query — and `WITH … DELETE` is caught by
# the forbidden-keyword scan below, which looks at the whole statement.
ALLOWED_OPENERS = frozenset({"select", "with", "values", "explain"})

# Scanned for anywhere in the statement, not just at the front. `attach` earns
# its place: it takes a plain path, and a plain path opens read-write even from
# a `mode=ro` connection, which would walk straight around layer 2. `pragma` is
# blocked because `writable_schema` is a pragma; the schema panel answers what
# `pragma table_info` would have been used for.
FORBIDDEN_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "replace",
    "drop",
    "alter",
    "create",
    "truncate",
    "attach",
    "detach",
    "vacuum",
    "reindex",
    "analyze",
    "pragma",
    "begin",
    "commit",
    "rollback",
    "savepoint",
    "release",
)
_FORBIDDEN_PATTERN = re.compile(rf"\b({'|'.join(FORBIDDEN_KEYWORDS)})\b", re.IGNORECASE)

DEFAULT_ROW_LIMIT = 500
MAX_ROW_LIMIT = 10_000
TIMEOUT_SECONDS = 5.0

# How often SQLite checks the deadline, in VM instructions. Low enough that a
# runaway query is stopped promptly, high enough that the callback is noise.
_PROGRESS_INTERVAL = 1_000


class SqlConsoleError(Exception):
    """A query this console refuses to run, or one that failed while running.

    Carries a message meant to be shown to the user as-is — the router turns it
    into a 400 and the editor prints it under the statement.
    """


@dataclass(frozen=True)
class QueryResult:
    """One statement's output, already capped at the requested row limit."""

    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool
    elapsed_ms: int


def mask_literals(sql: str) -> str:
    """Blank out string literals, quoted identifiers and comments.

    Returns a string of the same length as `sql` with those regions replaced by
    spaces, so offsets still line up and the result can be scanned for keywords
    without a `Verwendungszweck` like `'DROP TABLE'` tripping the check.
    """
    out: list[str] = []
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]

        # Quoted regions. SQLite escapes the quote by doubling it, and `[…]`
        # and backticks are accepted as identifier quoting for compatibility.
        if char in "'\"`[":
            closing = "]" if char == "[" else char
            out.append(" ")
            index += 1
            while index < length:
                if sql[index] == closing:
                    doubled = index + 1 < length and sql[index + 1] == closing
                    if doubled and closing != "]":
                        out.append("  ")
                        index += 2
                        continue
                    out.append(" ")
                    index += 1
                    break
                out.append("\n" if sql[index] == "\n" else " ")
                index += 1
            continue

        if char == "-" and sql.startswith("--", index):
            while index < length and sql[index] != "\n":
                out.append(" ")
                index += 1
            continue

        if char == "/" and sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            stop = length if end == -1 else end + 2
            while index < stop:
                out.append("\n" if sql[index] == "\n" else " ")
                index += 1
            continue

        out.append(char)
        index += 1

    return "".join(out)


def split_statements(sql: str) -> list[str]:
    """Split on semicolons that are not inside a literal or a comment.

    Empty fragments are dropped, so a trailing `;` — which everyone types — does
    not read as a second, empty statement.
    """
    masked = mask_literals(sql)
    statements: list[str] = []
    start = 0

    for index, char in enumerate(masked):
        if char == ";":
            if masked[start:index].strip():
                statements.append(sql[start:index].strip())
            start = index + 1

    if masked[start:].strip():
        statements.append(sql[start:].strip())

    return statements


def validate(sql: str) -> str:
    """Return the single read-only statement in `sql`, or raise `SqlConsoleError`."""
    statements = split_statements(sql)

    if not statements:
        raise SqlConsoleError("Query is empty.")
    if len(statements) > 1:
        raise SqlConsoleError(
            f"Only one statement per query — found {len(statements)}. "
            "Run them one at a time, or open a second tab."
        )

    statement = statements[0]
    masked = mask_literals(statement)

    opener = masked.strip().split(None, 1)[0].lower() if masked.strip() else ""
    if opener not in ALLOWED_OPENERS:
        raise SqlConsoleError(
            f"Only read-only queries are allowed here, and this one starts with "
            f"'{opener.upper()}'. Statements must begin with "
            f"{', '.join(sorted(word.upper() for word in ALLOWED_OPENERS))}."
        )

    forbidden = _FORBIDDEN_PATTERN.search(masked)
    if forbidden is not None:
        raise SqlConsoleError(
            f"'{forbidden.group(1).upper()}' is not allowed — this console reads, "
            "it never writes. Schema and data changes go through a migration."
        )

    return statement


def _encode(value: Any) -> Any:
    """Make one cell JSON-safe without reinterpreting it.

    Values are handed back as SQLite stored them. In particular `amount` is
    INTEGER cents (see "Money representation" in CLAUDE.md) and is *not*
    silently divided here — an arbitrary query can compute anything, and
    guessing which integers are money would corrupt the ones that are not. The
    schema panel labels the column instead.
    """
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    return value


def run_query(
    connection: Connection,
    sql: str,
    limit: int = DEFAULT_ROW_LIMIT,
    timeout_seconds: float = TIMEOUT_SECONDS,
) -> QueryResult:
    """Validate and execute one read-only statement.

    `limit` caps the rows returned, not the rows the query visits: one extra row
    is fetched to detect truncation, and the rest of the result set is simply
    never read.
    """
    statement = validate(sql)
    limit = max(1, min(limit, MAX_ROW_LIMIT))

    driver_connection = connection.connection.driver_connection
    deadline = time.monotonic() + timeout_seconds
    started = time.perf_counter()

    def abort_when_overdue() -> int:
        """Non-zero aborts the running statement. SQLite calls this every
        `_PROGRESS_INTERVAL` VM steps, which is the only way to interrupt a
        query that has not returned a row yet."""
        return 1 if time.monotonic() > deadline else 0

    if driver_connection is not None:
        driver_connection.set_progress_handler(abort_when_overdue, _PROGRESS_INTERVAL)

    try:
        # `exec_driver_sql` hands the text straight to the driver. `text()` would
        # parse `:name` as a bind parameter, so any query containing a colon —
        # a cast, a time literal — would fail on a parameter it never had.
        result = connection.exec_driver_sql(statement)
        columns = list(result.keys())
        fetched = result.fetchmany(limit + 1)
        result.close()
    except Exception as exc:  # noqa: BLE001 — the driver's message is the useful part
        if time.monotonic() > deadline:
            raise SqlConsoleError(
                f"Query cancelled after {timeout_seconds:.0f} s. Narrow it down "
                "with a date range or a LIMIT."
            ) from exc
        # SQLAlchemy wraps the driver error in a paragraph with the statement and
        # a documentation link. `orig` is the one line the user needs: "no such
        # table: transaktionen".
        raise SqlConsoleError(str(getattr(exc, "orig", None) or exc)) from exc
    finally:
        if driver_connection is not None:
            driver_connection.set_progress_handler(None, 0)

    truncated = len(fetched) > limit
    rows = [[_encode(value) for value in row] for row in fetched[:limit]]

    return QueryResult(
        columns=columns,
        rows=rows,
        row_count=len(rows),
        truncated=truncated,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
    )
