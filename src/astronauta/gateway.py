"""Transport-neutral application capabilities over the canonical okf-parser API.

Astronauta presentation code should depend on these capabilities rather than on
Markdown parsing, Ibis expressions, MCP tool names, GraphQL query documents, or
filesystem mutation. The module intentionally remains a thin read adapter: all
OKF semantics come from :mod:`okf_parser`.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from okf_parser import load_bundle
from okf_parser.service import schema_bundle


def _json_cell(value: Any) -> Any:
    """Normalize pandas' nullable-string float sentinel into JSON ``null``."""
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _records(table: Any) -> list[dict[str, Any]]:
    """Materialize an Ibis relation into deterministic JSON-friendly records."""
    rows = table.execute().to_dict(orient="records")
    return [{key: _json_cell(value) for key, value in row.items()} for row in rows]


def _sort_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _diagnostic_record(diagnostic: Any) -> dict[str, Any]:
    severity = diagnostic.severity
    return {
        "code": diagnostic.code,
        "severity": severity.value if hasattr(severity, "value") else str(severity),
        "path": diagnostic.path,
        "message": diagnostic.message,
    }


def _concept_record(row: dict[str, Any]) -> dict[str, Any]:
    """Serialize one canonical concept row without adding semantic inference."""
    raw_frontmatter = row.get("frontmatter_json")
    frontmatter = json.loads(raw_frontmatter) if isinstance(raw_frontmatter, str) else {}
    concept = {
        "id": row["concept_id"],
        "logical_key": row.get("logical_key"),
        "path": row["path"],
        "type": row["concept_type"],
        "title": row.get("title"),
        "description": row.get("description"),
        "frontmatter": frontmatter,
        "body": row.get("body") or "",
    }
    for key in ("source_digest", "revision_digest"):
        if key in row:
            concept[key] = row[key]
    return concept


def _load_state(root: Path) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
    bundle = load_bundle(root.resolve())
    concepts = sorted(
        (_concept_record(row) for row in _records(bundle.concepts)),
        key=lambda item: (_sort_text(item["path"]), _sort_text(item["id"])),
    )
    links = sorted(
        _records(bundle.links),
        key=lambda item: (
            _sort_text(item.get("source_id")),
            _sort_text(item.get("target_id")),
            _sort_text(item.get("raw_target")),
            _sort_text(item.get("origin")),
        ),
    )
    return bundle, concepts, links


def summary(root: Path) -> dict[str, Any]:
    """Return live bundle-level state derived only from canonical parser data."""
    bundle, concept_rows, links = _load_state(root)
    type_counts = Counter(item["type"] for item in concept_rows)
    return {
        "root": str(bundle.root),
        "markdown_count": bundle.markdown_count,
        "total_concepts": len(concept_rows),
        "total_reserved": len(_records(bundle.reserved)),
        "total_links": len(links),
        "is_conformant": bundle.is_conformant,
        "diagnostics_count": len(bundle.diagnostics),
        "concepts_by_type": dict(sorted(type_counts.items())),
    }


def concepts(root: Path, *, concept_type: str | None = None) -> list[dict[str, Any]]:
    """Return a deterministic live concept collection, optionally by exact type."""
    _, concept_rows, _ = _load_state(root)
    if concept_type is None:
        return concept_rows
    return [item for item in concept_rows if item["type"] == concept_type]


def concept(root: Path, concept_id: str) -> dict[str, Any] | None:
    """Return one concept plus canonical forward/reverse link records."""
    bundle, concept_rows, links = _load_state(root)
    selected = next((item for item in concept_rows if item["id"] == concept_id), None)
    if selected is None:
        return None

    selected = dict(selected)
    selected["outgoing_links"] = [item for item in links if item.get("source_id") == concept_id]
    selected["incoming_links"] = [item for item in links if item.get("target_id") == concept_id]
    selected["diagnostics"] = [
        _diagnostic_record(item)
        for item in bundle.diagnostics
        if item.path == selected["path"]
    ]
    return selected


def schemas(root: Path, *, spec_template: str | None = None) -> dict[str, Any]:
    """Return the parser's canonical JSON Schema contracts without type inference.

    Declared ``.schema.sql`` discovery is opt-in because RFC 0006 treats those
    files as trusted DuckDB SQL. The template is process/operator configuration,
    never a browser-supplied capability argument.
    """
    payload = schema_bundle(
        str(root.resolve()),
        fmt="json",
        infer_types=False,
        spec_template=spec_template,
    )
    if not isinstance(payload, dict):
        raise TypeError("okf-parser JSON schema service returned a non-object payload")
    return payload


def diagnostics(root: Path) -> list[dict[str, Any]]:
    """Return deterministic parser diagnostics without reclassifying severity."""
    bundle = load_bundle(root.resolve())
    return [_diagnostic_record(item) for item in bundle.validate()]


def graph(root: Path) -> dict[str, Any]:
    """Return canonical concept nodes plus resolved and unresolved link records."""
    _, concept_rows, links = _load_state(root)
    concept_ids = {item["id"] for item in concept_rows}
    resolved = [
        item
        for item in links
        if isinstance(item.get("target_id"), str) and item["target_id"] in concept_ids
    ]
    unresolved = [item for item in links if item not in resolved]
    return {
        "nodes": [
            {
                "id": item["id"],
                "path": item["path"],
                "type": item["type"],
                "title": item["title"],
            }
            for item in concept_rows
        ],
        "edges": resolved,
        "unresolved": unresolved,
    }


def snapshot(root: Path) -> dict[str, Any]:
    """Convenience projection for early UI migration; not a second domain model."""
    return {
        "summary": summary(root),
        "concepts": concepts(root),
        "diagnostics": diagnostics(root),
        "graph": graph(root),
    }


def read(
    root: Path,
    capability: str,
    *,
    concept_id: str | None = None,
    concept_type: str | None = None,
    spec_template: str | None = None,
) -> Any:
    """Dispatch a small capability vocabulary for process/HTTP/GraphQL adapters."""
    if capability == "summary":
        return summary(root)
    if capability == "concepts":
        return concepts(root, concept_type=concept_type)
    if capability == "concept":
        if not concept_id:
            raise ValueError("concept capability requires concept_id")
        return concept(root, concept_id)
    if capability == "schema":
        return schemas(root, spec_template=spec_template)
    if capability == "diagnostics":
        return diagnostics(root)
    if capability == "graph":
        return graph(root)
    if capability == "snapshot":
        return snapshot(root)
    raise ValueError(f"unknown gateway capability: {capability}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read Astronauta OKF gateway capabilities as JSON")
    parser.add_argument("root", type=Path, help="OKF bundle root")
    parser.add_argument(
        "capability",
        choices=("summary", "concepts", "concept", "schema", "diagnostics", "graph", "snapshot"),
    )
    parser.add_argument("--concept-id")
    parser.add_argument("--type", dest="concept_type")
    parser.add_argument(
        "--spec-template",
        help="opt into trusted RFC 0006 .schema.sql discovery using this type-spec template",
    )
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = read(
        args.root,
        args.capability,
        concept_id=args.concept_id,
        concept_type=args.concept_type,
        spec_template=args.spec_template,
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
