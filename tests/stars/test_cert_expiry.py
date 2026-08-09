from datetime import UTC, datetime

from stars.builtins import builtin_registry
from stars.cert_expiry.contract import tool_schemas
from stars.cert_expiry.service import inspect
from stars.cert_expiry.skill import build_skill


def _probe(host: str, *, port: int, timeout: float):
    assert (host, port, timeout) == ("orrery.lol", 443, 8)
    return (
        {
            "notBefore": "Aug 01 00:00:00 2026 GMT",
            "notAfter": "Sep 01 00:00:00 2026 GMT",
            "issuer": ((("commonName", "Test CA"),),),
            "subject": ((("commonName", "orrery.lol"), ("organizationName", "Orrery")),),
        },
        b"certificate",
    )


def test_allowlisted_tls_metadata_uses_sni_probe_seam() -> None:
    result = inspect("orrery-public", probe=_probe, clock=lambda: datetime(2026, 8, 9, tzinfo=UTC))
    assert result["host"] == "orrery.lol" and result["port"] == 443
    assert result["issuer"] == {"common_name": "Test CA"}
    assert result["subject"] == {"common_name": "orrery.lol", "organization": "Orrery"}
    assert result["days_until_expiry"] == 23 and result["sha256_fingerprint"].startswith("sha256:")


def test_unknown_host_is_rejected_without_probe() -> None:
    assert inspect("example.com")["error"] == "host_not_allowed"


def test_package_contract_and_discovery() -> None:
    assert set(tool_schemas()) == {"inspect"}
    assert {item.name for item in build_skill()._pending} == {"inspect"}
    assert (
        next(
            item for item in builtin_registry() if item.name == "orrery/cert-expiry"
        ).direct_mcp_path
        == "/stars/cert-expiry/mcp"
    )
