"""Refetch known listing URLs; promote and quiet on the live digest (#460)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .ping import ping_listing
from .promote import (
    DEFAULT_MAX_BROKEN_RATIO,
    DEFAULT_MIN_CALLERS,
    DEFAULT_MIN_USEFUL,
    apply_promotion,
    apply_quiet,
)
from .schema import ListingError
from .store import ListingStore, list_urls, listing_store_from_env, record_fetch_error


@dataclass(frozen=True, slots=True)
class RefetchResult:
    """Per-run outcome for tests (no scheduler)."""

    urls: tuple[str, ...]
    fetched: tuple[str, ...]
    promoted: tuple[str, ...]
    quieted: tuple[str, ...]
    errors: tuple[tuple[str, str], ...]


def refetch_known(
    *,
    fetch: Callable[[str], bytes] | None = None,
    store: ListingStore | None = None,
    min_useful: int = DEFAULT_MIN_USEFUL,
    min_callers: int = DEFAULT_MIN_CALLERS,
    max_broken_ratio: float = DEFAULT_MAX_BROKEN_RATIO,
) -> RefetchResult:
    """Refetch **only** stored ``listing_url``s. Never discovers hosts."""
    target = store if store is not None else listing_store_from_env()
    urls = list_urls(store=target)
    fetched: list[str] = []
    promoted: list[str] = []
    quieted: list[str] = []
    errors: list[tuple[str, str]] = []

    for url in urls:
        live_name: str | None = None
        try:
            record = ping_listing(url, fetch=fetch, store=target)
            fetched.append(url)
            live_name = record.name
        except ListingError as exc:
            errors.append((url, exc.code))
            record_fetch_error(url, exc.code, store=target)
            row = target.get(url)
            live_name = row.live_name if row is not None else None

        if not live_name:
            continue

        moved = apply_promotion(
            live_name,
            min_useful=min_useful,
            min_callers=min_callers,
            max_broken_ratio=max_broken_ratio,
        )
        if moved is not None:
            promoted.append(moved.name)

        if apply_quiet(url, max_broken_ratio=max_broken_ratio, store=target):
            quieted.append(live_name)

    return RefetchResult(
        urls=urls,
        fetched=tuple(fetched),
        promoted=tuple(promoted),
        quieted=tuple(quieted),
        errors=tuple(errors),
    )
