"""CLI and Generator for Astronauta Admin Panel."""
from pathlib import Path
import json
import typer
from rich.console import Console

from okf_parser import load_bundle

app = typer.Typer(help="Astronauta - OKF Admin Panel Generator")

@app.command()
def main(
    bundle_path: Path = typer.Argument(..., help="Path to OKF bundle directory"),
    output_dir: Path = typer.Option(Path("src/data"), "--out", "-o", help="Output directory for generated ASTRO data"),
):
    """Parses an OKF bundle using okf-parser and exports JSON data for Astro admin panel."""
    console = Console()
    bundle_path = bundle_path.resolve()
    if not bundle_path.exists():
        console.print(f"[bold red]Error:[/bold red] Bundle path '{bundle_path}' does not exist.")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Parsing OKF bundle from:[/bold cyan] {bundle_path}")
    
    bundle = load_bundle(bundle_path)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert ibis tables to pandas dataframes
    df_concepts = bundle.concepts.to_pandas()
    df_links = bundle.links.to_pandas()
    
    # Build NetworkX graph from bundle links
    graph = bundle.to_networkx()
    
    # 2. Concepts Data
    concepts_list = []
    type_counts = {}

    for _, row in df_concepts.iterrows():
        c_id = row.get('concept_id', row.get('id', ''))
        frontmatter = row.get('frontmatter', {})
        if isinstance(frontmatter, str):
            try:
                frontmatter = json.loads(frontmatter)
            except Exception:
                frontmatter = {}
        elif not isinstance(frontmatter, dict):
            frontmatter = {}

        ctype = frontmatter.get('type', row.get('type', 'unknown'))
        if not ctype or ctype == 'unknown':
            # Infer type from folder path (e.g. regras-sisprev/regras/regra-0001.md -> regra)
            rel_path = str(row.get('path', ''))
            parts = rel_path.split('/')
            if len(parts) > 1:
                ctype = parts[-2]
            else:
                ctype = 'concept'

        type_counts[ctype] = type_counts.get(ctype, 0) + 1

        in_links = [u for u, v in graph.in_edges(c_id)] if graph.has_node(c_id) else []
        out_links = [v for u, v in graph.out_edges(c_id)] if graph.has_node(c_id) else []
        
        concepts_list.append({
            "id": c_id,
            "path": row.get('path', ''),
            "title": frontmatter.get('title', c_id),
            "type": ctype,
            "frontmatter": frontmatter,
            "body": row.get('body', ''),
            "incoming_links": in_links,
            "outgoing_links": out_links,
        })

    # 1. Summary Data
    summary_data = {
        "root": str(bundle_path),
        "markdown_count": bundle.markdown_count,
        "total_concepts": len(df_concepts),
        "total_links": len(df_links),
        "is_conformant": bundle.is_conformant,
        "diagnostics_count": len(bundle.diagnostics),
        "concepts_by_type": type_counts,
    }

    # 3. Graph Nodes and Edges Data
    graph_edges = []
    for edge in graph.edges:
        u, v = edge[0], edge[1]
        graph_edges.append({"source": u, "target": v})

    graph_data = {
        "nodes": [{"id": n, "label": n} for n in graph.nodes],
        "edges": graph_edges,
    }
    
    # 4. Diagnostics / Violations Data
    diagnostics_list = [
        {
            "code": diag.code,
            "severity": diag.severity.value if hasattr(diag.severity, "value") else str(diag.severity),
            "path": diag.path,
            "message": diag.message,
        }
        for diag in bundle.diagnostics
    ]
    
    # Write JSON files
    (output_dir / "summary.json").write_text(json.dumps(summary_data, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "concepts.json").write_text(json.dumps(concepts_list, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "graph.json").write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "diagnostics.json").write_text(json.dumps(diagnostics_list, indent=2, ensure_ascii=False), encoding="utf-8")
    
    console.print(f"[bold green]Successfully generated Astro data in:[/bold green] {output_dir}")
    console.print(f" - [white]Concepts:[/white] {len(concepts_list)}")
    console.print(f" - [white]Links:[/white] {len(df_links)}")
    console.print(f" - [white]Diagnostics:[/white] {len(diagnostics_list)}")

if __name__ == "__main__":
    app()
