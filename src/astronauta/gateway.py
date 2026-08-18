"""Transport-neutral application capabilities over the canonical okf-parser API.

Astronauta presentation code depends on these capabilities rather than on
Markdown parsing, Ibis expressions, MCP tool names, GraphQL query documents, or
filesystem mutation. GraphQL is the preferred concept-read adapter behind this
boundary; schema, global diagnostics, summary-only aggregates, and writes retain
their dedicated parser-owned surfaces where the current GraphQL slice does not
model them yet.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from okf_parser import GraphQLReadAdapter, load_bundle
from okf_parser.service import schema_bundle

_GRAPHQL_PAGE_SIZE = 1000
_CONCEPTS_QUERY = """
query AstronautaConcepts($type: String, $first: Int!, $offset: Int!) {
  concepts(type: $type, first: $first, offset: $offset) {
    id
    logicalKey
    path
    type
    title
    description
    frontmatter
    body
    sourceDigest
    parsedDigest
  }
}
"""
_CONCEPT_QUERY = """
query AstronautaConcept($id: ID!) {
  concept(id: $id) {
    id
    logicalKey
    path
    type
    title
    description
    frontmatter
    body
    sourceDigest
    parsedDigest
    links { sourceId rawTarget targetId exists origin }
    reverseLinks { sourceId rawTarget targetId exists origin }
    diagnostics { code severity path message }
  }
}
"""
_GRAPH_QUERY = """
query AstronautaGraph($first: Int!, $offset: Int!) {
  concepts(first: $first, offset: $offset) {
    id
    path
    type
    title
    links { sourceId rawTarget targetId exists origin }
  }
}
"""


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


def _graphql_concept_record(row: dict[str, Any]) -> dict[str, Any]:
    """Map the parser GraphQL projection back to Astronauta's stable capability shape."""
    frontmatter = row.get("frontmatter")
    return {
        "id": row["id"],
        "logical_key": row.get("logicalKey"),
        "path": row["path"],
        "type": row["type"],
        "title": row.get("title"),
        "description": row.get("description"),
        "frontmatter": frontmatter if isinstance(frontmatter, dict) else {},
        "body": row.get("body") or "",
        "source_digest": row.get("sourceDigest"),
        "parsed_digest": row.get("parsedDigest"),
    }


def _graphql_link_record(row: dict[str, Any]) -> dict[str, Any]:
    """Keep GraphQL transport naming out of the public Astronauta capability contract."""
    return {
        "source_id": row["sourceId"],
        "raw_target": row["rawTarget"],
        "target_id": row.get("targetId"),
        "exists": bool(row["exists"]),
        "origin": row["origin"],
    }


def _graphql_data(
    adapter: GraphQLReadAdapter,
    query: str,
    variables: dict[str, object],
) -> dict[str, Any]:
    result = adapter.execute(query, variables)
    if result.errors:
        raise RuntimeError("okf-parser GraphQL read failed: " + "; ".join(result.errors))
    if result.data is None:
        raise RuntimeError("okf-parser GraphQL read returned no data")
    return result.data


def _graphql_collection(
    root: Path,
    *,
    concept_type: str | None = None,
) -> list[dict[str, Any]]:
    """Read one live concept snapshot through the embedded GraphQL adapter."""
    adapter = GraphQLReadAdapter(str(root.resolve()))
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        data = _graphql_data(
            adapter,
            _CONCEPTS_QUERY,
            {"type": concept_type, "first": _GRAPHQL_PAGE_SIZE, "offset": offset},
        )
        page = data.get("concepts")
        if not isinstance(page, list):
            raise TypeError("okf-parser GraphQL concepts query returned a non-list payload")
        for item in page:
            if not isinstance(item, dict):
                raise TypeError("okf-parser GraphQL concepts query returned a non-object row")
            rows.append(_graphql_concept_record(item))
        if len(page) < _GRAPHQL_PAGE_SIZE:
            break
        offset += len(page)
    return sorted(
        rows,
        key=lambda item: (_sort_text(item["path"]), _sort_text(item["id"])),
    )


def _load_state(root: Path) -> tuple[Any, list[dict[str, Any]], list[dict[str, Any]]]:
    """Load direct parser state only for aggregates not yet in the GraphQL read slice."""
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
    """Return the live concept collection through the preferred GraphQL read adapter."""
    return _graphql_collection(root, concept_type=concept_type)


def concept(root: Path, concept_id: str) -> dict[str, Any] | None:
    """Return one live concept plus canonical links and diagnostics through GraphQL."""
    adapter = GraphQLReadAdapter(str(root.resolve()))
    data = _graphql_data(adapter, _CONCEPT_QUERY, {"id": concept_id})
    row = data.get("concept")
    if row is None:
        return None
    if not isinstance(row, dict):
        raise TypeError("okf-parser GraphQL concept query returned a non-object payload")

    selected = _graphql_concept_record(row)
    outgoing = row.get("links")
    incoming = row.get("reverseLinks")
    findings = row.get("diagnostics")
    if not isinstance(outgoing, list) or not isinstance(incoming, list) or not isinstance(findings, list):
        raise TypeError("okf-parser GraphQL concept detail returned malformed related records")

    selected["outgoing_links"] = sorted(
        (_graphql_link_record(item) for item in outgoing if isinstance(item, dict)),
        key=lambda item: (
            _sort_text(item.get("source_id")),
            _sort_text(item.get("target_id")),
            _sort_text(item.get("raw_target")),
            _sort_text(item.get("origin")),
        ),
    )
    selected["incoming_links"] = sorted(
        (_graphql_link_record(item) for item in incoming if isinstance(item, dict)),
        key=lambda item: (
            _sort_text(item.get("source_id")),
            _sort_text(item.get("target_id")),
            _sort_text(item.get("raw_target")),
            _sort_text(item.get("origin")),
        ),
    )
    selected["diagnostics"] = [dict(item) for item in findings if isinstance(item, dict)]
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
    """Return global parser diagnostics until GraphQL exposes a bundle-level query."""
    bundle = load_bundle(root.resolve())
    return [_diagnostic_record(item) for item in bundle.validate()]


def graph(root: Path) -> dict[str, Any]:
    """Return graph projection through the preferred GraphQL concept/link adapter."""
    adapter = GraphQLReadAdapter(str(root.resolve()))
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        data = _graphql_data(
            adapter,
            _GRAPH_QUERY,
            {"first": _GRAPHQL_PAGE_SIZE, "offset": offset},
        )
        page = data.get("concepts")
        if not isinstance(page, list):
            raise TypeError("okf-parser GraphQL graph query returned a non-list payload")
        for item in page:
            if not isinstance(item, dict):
                raise TypeError("okf-parser GraphQL graph query returned a non-object row")
            rows.append(item)
        if len(page) < _GRAPHQL_PAGE_SIZE:
            break
        offset += len(page)

    nodes = sorted(
        (
            {
                "id": item["id"],
                "path": item["path"],
                "type": item["type"],
                "title": item.get("title"),
            }
            for item in rows
        ),
        key=lambda item: (_sort_text(item["path"]), _sort_text(item["id"])),
    )
    links = sorted(
        (
            _graphql_link_record(link)
            for item in rows
            for link in item.get("links", [])
            if isinstance(link, dict)
        ),
        key=lambda item: (
            _sort_text(item.get("source_id")),
            _sort_text(item.get("target_id")),
            _sort_text(item.get("raw_target")),
            _sort_text(item.get("origin")),
        ),
    )
    node_ids = {item["id"] for item in nodes}
    resolved = [
        item
        for item in links
        if isinstance(item.get("target_id"), str) and item["target_id"] in node_ids
    ]
    unresolved = [item for item in links if item not in resolved]
    return {"nodes": nodes, "edges": resolved, "unresolved": unresolved}


def snapshot(root: Path) -> dict[str, Any]:
    """Convenience projection for UI migration; not a second domain model."""
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
    """Dispatch a small capability vocabulary independent of its internal adapter."""
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
