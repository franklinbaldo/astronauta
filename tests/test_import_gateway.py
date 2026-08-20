from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from astronauta.gateway_http import GatewayServer


class ImportGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        imports = self.root / "imports"
        imports.mkdir()
        self.source = imports / "notes.csv"
        self.source.write_text("slug,title\nalpha,Alpha\nbeta,Beta\n", encoding="utf-8")
        self.server: GatewayServer | None = None
        self.thread: threading.Thread | None = None

    def tearDown(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def start(self, *, allow_write: bool) -> str:
        self.server = GatewayServer(("127.0.0.1", 0), self.root, allow_write=allow_write)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/gateway"

    def post(self, url: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        request = Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())
        with response:
            return response.status, json.loads(response.read())

    @staticmethod
    def request_payload(capability: str) -> dict[str, object]:
        return {
            "capability": capability,
            "source": "imports/notes.csv",
            "concept_type": "Note",
            "id_column": "slug",
            "overwrite": False,
            "on_conflict": "skip",
        }

    def test_import_preview_is_available_without_write_and_does_not_mutate(self) -> None:
        url = self.start(allow_write=False)

        status, payload = self.post(url, self.request_payload("import_preview"))

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(result["would_create"], ["note/alpha.md", "note/beta.md"])
        self.assertFalse(result["written"])
        self.assertFalse((self.root / "note").exists())

    def test_browser_payload_cannot_grant_import_write_authority(self) -> None:
        url = self.start(allow_write=False)
        request = self.request_payload("import_write")
        request["allow_write"] = True

        status, payload = self.post(url, request)

        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "WriteCapabilityDisabled")
        self.assertFalse((self.root / "note").exists())

    def test_write_enabled_process_commits_exact_parser_import(self) -> None:
        url = self.start(allow_write=True)

        status, payload = self.post(url, self.request_payload("import_write"))

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(result["created"], ["note/alpha.md", "note/beta.md"])
        self.assertTrue(result["written"])
        alpha = (self.root / "note" / "alpha.md").read_text(encoding="utf-8")
        self.assertIn("type: Note", alpha)
        self.assertIn("slug: alpha", alpha)
        self.assertIn("title: Alpha", alpha)

    def test_import_source_cannot_escape_bundle_root(self) -> None:
        url = self.start(allow_write=False)
        request = self.request_payload("import_preview")
        request["source"] = "../outside.csv"

        status, payload = self.post(url, request)

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "ValueError")
        self.assertIn("inside the bundle root", str(payload["message"]))

    def test_import_source_rejects_unsupported_extension_before_parser(self) -> None:
        (self.root / "imports" / "secret.txt").write_text("x", encoding="utf-8")
        url = self.start(allow_write=False)
        request = self.request_payload("import_preview")
        request["source"] = "imports/secret.txt"

        status, payload = self.post(url, request)

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "ValueError")
        self.assertIn("CSV, JSON/NDJSON, or Parquet", str(payload["message"]))


if __name__ == "__main__":
    unittest.main()
