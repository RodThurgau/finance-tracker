"""Rows that are one leg of a transfer between the user's own accounts.

A single PayPal purchase reaches the database three times:

| Source | Row                                                  | Amount |
|--------|------------------------------------------------------|--------|
| PayPal | `Intelligent Apps GmbH` (the actual purchase)        | -37.50 |
| PayPal | `Bankgutschrift auf PayPal-Konto` (funds it)         | +37.50 |
| ING    | `PayPal Europe S.a.r.l. et Cie S.C.A` (funds *that*) | -37.50 |

Only the first is a real expense; the other two are the money moving between
the user's own accounts to settle it. Dropping both leaves exactly one copy of
the amount, and it is the useful copy — the PayPal row names the real merchant,
while the ING row only ever says "PayPal Europe".

**Both legs must be dropped together.** Dropping only one leaves the totals
wrong in the other direction, which is why they share this one definition
rather than being filtered ad hoc at each call site.

This is deliberately *not* `exclude_from_stats`: that flag is user-owned and
never written by the app (CLAUDE.md), and it intentionally does not affect the
transaction list. Internal transfers are derived from the row's own contents
instead, evaluated at query time. Nothing is stored, so re-tuning the match
below takes effect immediately, with no migration and no stale flags on rows
imported under an older definition.
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, or_

from models import Transaction

# ING books PayPal funding debits against this counterparty. Matched as a
# case-insensitive substring rather than the full legal name, because the exact
# spelling varies between exports (the trailing dot on "S.C.A." comes and
# goes); anchoring on the brand keeps the match stable across those variants.
ING_PAYPAL_COUNTERPARTY = "paypal"

# PayPal's own funding leg: the credit that settles a card/express purchase,
# always the opposite sign of the purchase it is linked to through
# `Zugehöriger Transaktionscode`. The German-locale export is the only one this
# app supports (CLAUDE.md), so this label is stable.
PAYPAL_FUNDING_TYPE = "Bankgutschrift auf PayPal-Konto"


def is_internal_transfer() -> ColumnElement[bool]:
    """SQL predicate selecting the funding legs described in the module docstring.

    The `is_not(None)` guards are load-bearing: `NULL ILIKE '…'` is NULL, and a
    NULL inside this predicate would make `~is_internal_transfer()` NULL too —
    silently dropping every row with no counterparty (an ING `Wertpapierkauf`,
    say) from the list and from every total. With the guard the conjunction is
    FALSE rather than NULL, and those rows are kept.
    """
    return or_(
        and_(
            Transaction.source == "ING",
            Transaction.counter_account.is_not(None),
            Transaction.counter_account.ilike(f"%{ING_PAYPAL_COUNTERPARTY}%"),
        ),
        and_(
            Transaction.source == "PayPal",
            Transaction.transaction_type.is_not(None),
            Transaction.transaction_type.ilike(PAYPAL_FUNDING_TYPE),
        ),
    )
