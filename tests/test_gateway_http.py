from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from astronauta.gateway_http import GatewayServer


class GatewayHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "note.md").write_text(
            """---
type: Note
title: Hello
---
# Hello
""",
            encoding="utf-8",
        )
        self.server = GatewayServer(("127.0.0.1", 0), self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/gateway"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def post(self, payload: object) -> tuple[int, dict[str, object]]:
        request = Request(
            self.url,
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            response = urlopen(request, timeout=2)
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())
        with response:
            return response.status, json.loads(response.read())

    def test_transports_capability_result_without_new_domain_shape(self) -> None:
        status, payload = self.post({"capability": "concepts"})
        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, list)
        assert isinstance(result, list)
        self.assertEqual(result[0]["type"], "Note")
        self.assertEqual(result[0]["path"], "note.md")

    def test_rejects_unknown_capability_as_client_error(self) -> None:
        status, payload = self.post({"capability": "arbitrary-filesystem-operation"})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "ValueError")

    def test_rejects_non_string_selector_values(self) -> None:
        status, payload = self.post({"capability": "concept", "concept_id": ["not", "an", "id"]})
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "ValueError")


if __name__ == "__main__":
    unittest.main()
