"""Bounded write capabilities exposed by Astronauta's local application gateway.

Astronauta owns capability gating and transport only. Every OKF mutation is
performed by a public ``okf-parser`` service; this module never writes a bundle
file or serializes frontmatter itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from okf_parser.service import (
    apply_bundle,
    import_bundle,
    preview_concept_edit,
    write_concept_edit,
)

if TYPE_CHECKING:
    pass


class WriteCapabilityDisabled(PermissionError):
    """Raised when a commit capability is requested from a read-only runtime."""


def _required_string(payload: dict[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        msg = f"{name} must be a string"
        raise ValueError(msg)
    return value


def _optional_string(payload: dict[str, object], name: str) -> str | None:
    value = payload.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        msg = f"{name} must be a string"
        raise ValueError(msg)
    return value or None


def _optional_bool(payload: dict[str, object], name: str, *, default: bool = False) -> bool:
    value = payload.get(name, default)
    if not isinstance(value, bool):
        msg = f"{name} must be a boolean"
        raise ValueError(msg)
    return value


def _bounded_import_source(root: Path, payload: dict[str, object]) -> str:
    """Resolve a browser-selected source without granting arbitrary local-file reads."""
    source = Path(_required_string(payload, "source"))
    if source.is_absolute():
        raise ValueError("source must be a path relative to the bundle root")
    root = root.resolve()
    resolved = (root / source).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("source must remain inside the bundle root") from exc
    if resolved.suffix.lower() not in {".csv", ".json", ".jsonl", ".ndjson", ".parquet"}:
        raise ValueError("source must be CSV, JSON/NDJSON, or Parquet")
    if not resolved.is_file():
        raise ValueError("source does not exist inside the bundle root")
    return str(resolved)


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

    if capability in {"import_preview", "import_write"}:
        source = _bounded_import_source(root, payload)
        concept_type = _required_string(payload, "concept_type")
        id_column = _optional_string(payload, "id_column")
        overwrite = _optional_bool(payload, "overwrite")
        on_conflict = _optional_string(payload, "on_conflict") or "skip"
        if on_conflict not in {"skip", "verify-identical"}:
            raise ValueError("on_conflict must be 'skip' or 'verify-identical'")
        conflict_policy: Literal["skip", "verify-identical"] = on_conflict
        if capability == "import_write" and not allow_write:
            raise WriteCapabilityDisabled(
                "write capabilities are disabled; start Astronauta with --write"
            )
        return import_bundle(
            source,
            str(root),
            concept_type,
            id_column=id_column,
            write=capability == "import_write",
            overwrite=overwrite,
            on_conflict=conflict_policy,
        )

    msg = f"unknown mutation capability: {capability}"
    raise ValueError(msg)
