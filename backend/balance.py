"""Known real account balances, and the running balance derived from them.

The ledger records movements, not a balance — nothing in a CSV export says how
much is actually in the account. So the balance is anchored: one real,
hand-verified figure read off the bank at the end of a named day, plus every
movement recorded since.

    current balance = latest anchor + sum(transactions after the anchor's date)

**Anchors are how the data gets verified.** Add a new one each time the real
balance is checked against the bank, and `/stats/balance` reports, for every
consecutive pair, what the ledger *predicts* the later balance should be
against what was actually observed. A non-zero drift means the imported data
is incomplete or double-counted somewhere between those two dates — which is
the whole point of keeping more than one.

To add an anchor, append to `BALANCE_ANCHORS` below. Order does not matter;
the list is sorted on use.

**What counts toward the balance.** The same rows `/stats/summary` aggregates:
`exclude_from_stats` rows are left out (they are flagged precisely because they
double-count real money), and so are internal transfers. Dropping the funding
legs is safe here for the same reason it is safe there — a PayPal purchase and
the ING debit that settles it are the same money, and the pair nets to the
single amount either way. If that pairing ever breaks, the drift on the next
anchor is what surfaces it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal


@dataclass(frozen=True)
class BalanceAnchor:
    """A real balance, observed at the *end* of `on` — transactions dated `on`
    are already included in `balance`."""

    on: date_type
    balance: Decimal


# Verified against the bank. Append, never edit a past entry: an anchor that is
# adjusted to make a drift disappear destroys the only evidence that something
# was wrong.
BALANCE_ANCHORS: list[BalanceAnchor] = [
    BalanceAnchor(date_type(2026, 8, 10), Decimal("1608.90")),
]


def sorted_anchors() -> list[BalanceAnchor]:
    return sorted(BALANCE_ANCHORS, key=lambda anchor: anchor.on)
