"""Sortable identifiers (ULIDs) with a type prefix, e.g. ``run_01J…``.

IDs are monotonic within a process: two IDs created in the same millisecond still sort in
creation order (the 80-bit random part is incremented instead of redrawn).
"""

import threading
from typing import Final

from ulid import ULID

PREFIXES: Final = frozenset({"run", "task", "att", "gate", "evt", "exp"})

_RANDOM_BITS: Final = 80
_lock = threading.Lock()
_last: int = 0


def _next_ulid() -> ULID:
    global _last
    candidate = int(ULID())
    with _lock:
        if candidate >> _RANDOM_BITS <= _last >> _RANDOM_BITS:
            # Same (or earlier, on clock step-back) millisecond: stay monotonic.
            candidate = _last + 1
        _last = candidate
    return ULID.from_int(candidate)


def new_id(prefix: str) -> str:
    """Return ``f"{prefix}_{ULID()}"``. Raises ``ValueError`` for an unknown prefix."""
    if prefix not in PREFIXES:
        raise ValueError(f"unknown id prefix {prefix!r}; expected one of {sorted(PREFIXES)}")
    return f"{prefix}_{_next_ulid()}"
