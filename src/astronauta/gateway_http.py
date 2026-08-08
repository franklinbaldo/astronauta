"""Private loopback transport for Astronauta's application gateway.

This module is intentionally not a public REST API. It transports the small
capability vocabulary defined in :mod:`astronauta.gateway` so Astro can run in
a separate process while the final GraphQL/application packaging evolves.
"""

from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from astronauta.gateway import read

_LOOPBACK_HOST = "127.0.0.1"
_MAX_REQUEST_BYTES = 64 * 1024


class GatewayHandler(BaseHTTPRequestHandler):
    """Transport one capability request per POST without adding OKF semantics."""

    server: "GatewayServer"

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        if self.path != "/gateway":
            self._json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return

        try:
            length = int(self.headers.get("content-length", "0"))
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_content_length"})
            return
        if length <= 0 or length > _MAX_REQUEST_BYTES:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request_size"})
            return

        try:
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("request must be a JSON object")
            capability = payload.get("capability")
            if not isinstance(capability, str):
                raise ValueError("capability must be a string")
            concept_id = payload.get("concept_id")
            concept_type = payload.get("concept_type")
            if concept_id is not None and not isinstance(concept_id, str):
                raise ValueError("concept_id must be a string")
            if concept_type is not None and not isinstance(concept_type, str):
                raise ValueError("concept_type must be a string")
            # spec_template deliberately cannot come from the browser payload:
            # RFC 0006 declarations are trusted DuckDB SQL and must be opted in
            # by the operator when the local gateway process starts.
            result = read(
                self.server.bundle_root,
                capability,
                concept_id=concept_id,
                concept_type=concept_type,
                spec_template=self.server.spec_template,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": type(exc).__name__, "message": str(exc)},
            )
            return
        except Exception as exc:  # preserve failure instead of success-shaped fallback
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": type(exc).__name__, "message": str(exc)},
            )
            return

        self._json(HTTPStatus.OK, {"result": result})

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class GatewayServer(ThreadingHTTPServer):
    """HTTP server carrying immutable local operator configuration."""

    def __init__(
        self,
        address: tuple[str, int],
        bundle_root: Path,
        *,
        spec_template: str | None = None,
    ) -> None:
        super().__init__(address, GatewayHandler)
        self.bundle_root = bundle_root.resolve()
        self.spec_template = spec_template


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Astronauta gateway on loopback")
    parser.add_argument("root", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--spec-template",
        help="opt into trusted RFC 0006 .schema.sql discovery using this type-spec template",
    )
    args = parser.parse_args()

    server = GatewayServer(
        (_LOOPBACK_HOST, args.port),
        args.root,
        spec_template=args.spec_template,
    )
    host, port = server.server_address
    print(
        json.dumps(
            {
                "host": host,
                "port": port,
                "root": str(server.bundle_root),
                "spec_template": server.spec_template,
            }
        ),
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
