"""Bounded write capabilities exposed by Astronauta's local application gateway.

Astronauta owns capability gating and transport only. Every OKF mutation is
performed by a public ``okf-parser`` service; this module never writes a bundle
file or serializes frontmatter itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from okf_parser.service import apply_bundle, preview_concept_edit, write_concept_edit

if TYPE_CHECKING:
    from pathlib import Path


class WriteCapabilityDisabled(PermissionError):
    """Raised when a commit capability is requested from a read-only runtime."""


def _required_string(payload: dict[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        msg = f"{name} must be a string"
        raise ValueError(msg)
    return value


def dispatch_mutation(
    root: Path,
    capability: str,
    payload: dict[str, object],
    *,
    allow_write: bool,
    spec_template: str | None,
) -> dict[str, object]:
    """Dispatch one preview/commit operation without adding OKF semantics."""
    if capability in {"edit_preview", "edit_write"}:
        concept_id = _required_string(payload, "concept_id")
        body = _required_string(payload, "body")
        expected_source_digest = _required_string(payload, "expected_source_digest")
        if capability == "edit_write":
            if not allow_write:
                raise WriteCapabilityDisabled(
                    "write capabilities are disabled; start Astronauta with --write"
                )
            return write_concept_edit(
                str(root),
                concept_id,
                body,
                expected_source_digest,
            )
        return preview_concept_edit(
            str(root),
            concept_id,
            body,
            expected_source_digest,
        )

    if capability in {"apply_preview", "apply_write"}:
        sql = _required_string(payload, "sql")
        if capability == "apply_write":
            if not allow_write:
                raise WriteCapabilityDisabled(
                    "write capabilities are disabled; start Astronauta with --write"
                )
            preview_token = _required_string(payload, "preview_token")
            return apply_bundle(
                str(root),
                sql=sql,
                write=True,
                expected_preview_token=preview_token,
                spec_template=spec_template,
            )
        return apply_bundle(
            str(root),
            sql=sql,
            write=False,
            spec_template=spec_template,
        )

    msg = f"unknown mutation capability: {capability}"
    raise ValueError(msg)
