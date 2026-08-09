"""Allowlisted TLS certificate inspection; not a network scanner."""

from __future__ import annotations

import hashlib
import socket
import ssl
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Protocol

from .contract import DEFAULT_HOST, HOSTS

PORT = 443
TIMEOUT_SECONDS = 8


class Probe(Protocol):
    def __call__(
        self, hostname: str, *, port: int, timeout: float
    ) -> tuple[Mapping[str, object], bytes]: ...


def _network_probe(
    hostname: str, *, port: int, timeout: float
) -> tuple[Mapping[str, object], bytes]:
    context = ssl.create_default_context()
    with (
        socket.create_connection((hostname, port), timeout=timeout) as connection,
        context.wrap_socket(connection, server_hostname=hostname) as tls,
    ):
        return tls.getpeercert(), tls.getpeercert(binary_form=True)


def inspect(
    host: str = DEFAULT_HOST,
    *,
    probe: Probe = _network_probe,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    hostname = HOSTS.get(host)
    observed_at = (clock or (lambda: datetime.now(UTC)))()
    if hostname is None:
        return {"error": "host_not_allowed", "host": host, "live_at_call": True}
    try:
        certificate, der = probe(hostname, port=PORT, timeout=TIMEOUT_SECONDS)
        not_before = _certificate_time(certificate, "notBefore")
        not_after = _certificate_time(certificate, "notAfter")
    except (OSError, ssl.SSLError, ValueError, KeyError) as error:
        return {
            "error": "tls_unreachable",
            "host": host,
            "detail": str(error),
            "live_at_call": True,
        }
    return {
        "host": hostname,
        "port": PORT,
        "issuer": _summary(certificate.get("issuer")),
        "subject": _summary(certificate.get("subject")),
        "not_before": not_before.isoformat(),
        "not_after": not_after.isoformat(),
        "days_until_expiry": (not_after - observed_at).days,
        "sha256_fingerprint": f"sha256:{hashlib.sha256(der).hexdigest()}",
        "observed_at": observed_at.isoformat(),
        "live_at_call": True,
    }


def _certificate_time(certificate: Mapping[str, object], key: str) -> datetime:
    value = certificate.get(key)
    if not isinstance(value, str):
        raise ValueError(f"certificate missing {key}")
    return datetime.strptime(value, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)


def _summary(value: object) -> dict[str, str]:
    """Keep only first CN/O values, never arbitrary certificate extensions."""
    result: dict[str, str] = {}
    if not isinstance(value, tuple):
        return result
    for group in value:
        if not isinstance(group, tuple):
            continue
        for item in group:
            if (
                isinstance(item, tuple)
                and len(item) == 2
                and item[0] in {"commonName", "organizationName"}
            ):
                result.setdefault(
                    "common_name" if item[0] == "commonName" else "organization", str(item[1])[:256]
                )
    return result
