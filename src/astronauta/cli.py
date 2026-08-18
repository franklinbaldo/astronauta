"""Runtime command for Astronauta's live OKF admin."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from astronauta.runtime import RuntimeUnavailable, serve_admin

app = typer.Typer(
    help="Astronauta — live admin over an OKF bundle.",
    no_args_is_help=True,
)
console = Console()

_DEFAULT_WEB_PORT = 4321


@app.command()
def gateway(
    bundle_path: Path = typer.Argument(..., help="Path to the OKF bundle directory"),
    write: bool = typer.Option(
        False,
        "--write",
        help="Enable filesystem-changing parser capabilities for this process",
    ),
    port: int = typer.Option(
        _DEFAULT_WEB_PORT,
        "--port",
        min=1,
        max=65535,
        help="Loopback port for the browser-facing Astro application",
    ),
    spec_template: str | None = typer.Option(
        None,
        "--spec-template",
        help="Opt into trusted RFC 0006 .schema.sql discovery using this type-spec template",
    ),
) -> None:
    """Serve the complete local admin for an OKF bundle.

    The process is read-capable by default. ``--write`` is an operator-owned
    capability decision made before the gateway accepts requests; browser
    payloads cannot enable commit operations themselves.
    """
    root = bundle_path.expanduser().resolve()
    if not root.is_dir():
        raise typer.BadParameter(f"bundle path is not a directory: {root}", param_hint="bundle_path")

    def announce_ready() -> None:
        console.print(f"[bold cyan]Astronauta[/bold cyan] {root}")
        console.print(f"[bold]http://127.0.0.1:{port}/[/bold]")
        console.print(
            "[yellow]write capabilities enabled[/yellow]"
            if write
            else "[dim]read-only process profile[/dim]"
        )
        if spec_template:
            console.print(f"[yellow]trusted schema declarations enabled:[/yellow] {spec_template}")

    try:
        serve_admin(
            root,
            write=write,
            port=port,
            spec_template=spec_template,
            on_ready=announce_ready,
        )
    except RuntimeUnavailable as exc:
        console.print(f"[bold red]Astronauta could not start:[/bold red] {exc}")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
