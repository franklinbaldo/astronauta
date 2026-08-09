"""Runtime command for Astronauta's live OKF admin."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from astronauta.gateway_http import GatewayServer

app = typer.Typer(
    help="Astronauta — live admin over an OKF bundle.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def gateway(
    bundle_path: Path = typer.Argument(..., help="Path to the OKF bundle directory"),
    write: bool = typer.Option(
        False,
        "--write",
        help="Enable filesystem-changing parser capabilities for this process",
    ),
    port: int = typer.Option(8765, "--port", min=0, max=65535, help="Loopback gateway port"),
    spec_template: str | None = typer.Option(
        None,
        "--spec-template",
        help="Opt into trusted RFC 0006 .schema.sql discovery using this type-spec template",
    ),
) -> None:
    """Serve the local application gateway for an OKF bundle.

    The process is read-capable by default. ``--write`` is an operator-owned
    capability decision made before requests are accepted; browser payloads
    cannot enable commit operations themselves.
    """
    root = bundle_path.expanduser().resolve()
    if not root.is_dir():
        raise typer.BadParameter(f"bundle path is not a directory: {root}", param_hint="bundle_path")

    server = GatewayServer(
        ("127.0.0.1", port),
        root,
        spec_template=spec_template,
        allow_write=write,
    )
    host, bound_port = server.server_address
    console.print(f"[bold cyan]Astronauta[/bold cyan] {root}")
    console.print(f"[dim]http://{host}:{bound_port}/gateway[/dim]")
    console.print(
        "[yellow]write capabilities enabled[/yellow]" if write else "[dim]read-only process profile[/dim]"
    )
    if spec_template:
        console.print(f"[yellow]trusted schema declarations enabled:[/yellow] {spec_template}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    app()
