"""Chirp/MCP adapter for the html-to-pdf Star contract."""

from __future__ import annotations

import base64
from typing import Any

from chirp.skill import Skill

from stars.managed_api import ManagedStarService, configured_managed_service
from stars.signing import public_star_signing_key

from .artifacts import get_pdf_artifacts
from .contract import STAR_VERSION
from .service import convert as convert_html
from .service import health as health_check


def build_skill(
    *, private_key: Any | None = None, managed_service: ManagedStarService | None = None
) -> Skill:
    """Build the direct-endpoint html-to-pdf skill with canonical tool names."""
    private, key_id = public_star_signing_key(
        private_key=private_key,
        private_key_env="ORRERY_PDF_PRIVATE_KEY",
        key_id_env="ORRERY_PDF_KEY_ID",
        default_key_id="orrery-pdf-1",
    )
    skill = Skill(
        "html-to-pdf",
        version=STAR_VERSION,
        private_key=private,
        key_id=key_id,
        public_key=private.public_key().public_bytes_raw(),
    )

    @skill.tool(
        "convert",
        description=(
            "Render simple HTML to a short-lived PDF artifact synchronously; "
            "use for quick jobs when the caller can wait"
        ),
    )
    def convert(html: str) -> dict[str, object]:
        result = convert_html(html)
        encoded = str(result.pop("artifact_base64"))
        artifact = get_pdf_artifacts().publish(base64.b64decode(encoded, validate=True))
        result["artifact_url"] = f"/artifacts/{artifact.artifact_id}"
        result["sha256"] = artifact.sha256
        return result

    @skill.tool(
        "submit",
        description=(
            "Queue HTML-to-PDF on the managed worker; returns run_id and queued "
            "state — poll result(run_id) for the signed receipt"
        ),
    )
    def submit(html: str, idempotency_key: str) -> dict[str, object]:
        managed = managed_service or configured_managed_service()
        return managed.submit(
            kind="html-to-pdf", input={"html": html}, idempotency_key=idempotency_key
        )

    @skill.tool(
        "result",
        description=(
            "Poll a managed PDF run by run_id; unknown run_id returns "
            "error run_not_found"
        ),
    )
    def result(run_id: str) -> dict[str, object]:
        managed = managed_service or configured_managed_service()
        return managed.result(run_id)

    @skill.tool("health", description="html-to-pdf readiness probe")
    def health() -> dict[str, str]:
        return health_check()

    return skill
