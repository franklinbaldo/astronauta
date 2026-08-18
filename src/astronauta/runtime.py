"""Own Astronauta's local gateway and Astro process lifecycle."""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

from astronauta.gateway_http import GatewayServer

_LOOPBACK_HOST = "127.0.0.1"
_WEB_READY_TIMEOUT = 10.0
_CHILD_STOP_TIMEOUT = 5.0


class RuntimeUnavailable(RuntimeError):
    """The local web runtime cannot be started coherently."""


def _resolve_web_entry() -> Path:
    """Locate the standalone Astro entry without making it a CLI concern.

    The first candidate is the package-local slot reserved for the distribution
    slice of issue #7. The second is the normal repository build output used by
    source checkouts today. Keeping both behind this resolver means packaging
    can change without changing ``astronauta PATH [--write]``.
    """
    module = Path(__file__).resolve()
    candidates = (
        module.parent / "_web" / "server" / "entry.mjs",
        module.parents[2] / "dist" / "server" / "entry.mjs",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeUnavailable(
        "Astro standalone runtime not found. Build the source checkout with "
        "`bun run build`; packaged runtime assets are supplied by the distribution slice."
    )


def _node_executable() -> str:
    executable = shutil.which("node")
    if executable is None:
        raise RuntimeUnavailable("Node.js is required to serve the Astro standalone application")
    return executable


def _wait_for_web(
    process: subprocess.Popen[bytes],
    host: str,
    port: int,
    *,
    timeout: float = _WEB_READY_TIMEOUT,
) -> None:
    """Wait until Astro owns its loopback socket or fails clearly."""
    deadline = time.monotonic() + timeout
    while True:
        returncode = process.poll()
        if returncode is not None:
            raise RuntimeUnavailable(
                f"Astro standalone process exited before becoming ready (exit {returncode})"
            )
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            if time.monotonic() >= deadline:
                raise RuntimeUnavailable(
                    f"Astro standalone process did not become ready on http://{host}:{port}/"
                )
            time.sleep(0.05)


def _stop_child(process: subprocess.Popen[bytes]) -> None:
    """Stop the Astro child without leaving a background server behind."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=_CHILD_STOP_TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=_CHILD_STOP_TIMEOUT)


def serve_admin(
    root: Path,
    *,
    write: bool,
    port: int,
    spec_template: str | None,
    on_ready: Callable[[], None] | None = None,
) -> None:
    """Own the gateway + Astro lifecycle for one local admin invocation."""
    entry = _resolve_web_entry()
    node = _node_executable()

    server = GatewayServer(
        (_LOOPBACK_HOST, 0),
        root,
        spec_template=spec_template,
        allow_write=write,
    )
    gateway_host, gateway_port = server.server_address
    gateway_thread = threading.Thread(
        target=server.serve_forever,
        name="astronauta-gateway",
        daemon=False,
    )
    gateway_thread.start()

    environment = os.environ.copy()
    environment.update(
        {
            "ASTRONAUTA_GATEWAY_URL": f"http://{gateway_host}:{gateway_port}/gateway",
            "HOST": _LOOPBACK_HOST,
            "PORT": str(port),
        }
    )

    process: subprocess.Popen[bytes] | None = None
    previous_sigterm = signal.getsignal(signal.SIGTERM)

    def stop_on_sigterm(_signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_on_sigterm)
    try:
        process = subprocess.Popen(  # noqa: S603
            [node, str(entry)],
            cwd=entry.parents[2],
            env=environment,
        )
        _wait_for_web(process, _LOOPBACK_HOST, port)
        if on_ready is not None:
            on_ready()

        returncode = process.wait()
        if returncode != 0:
            raise RuntimeUnavailable(f"Astro standalone process exited with status {returncode}")
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        if process is not None:
            _stop_child(process)
        server.shutdown()
        server.server_close()
        gateway_thread.join(timeout=_CHILD_STOP_TIMEOUT)
