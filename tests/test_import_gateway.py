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

    def preview(self, url: str, *, overwrite: bool = False) -> tuple[dict[str, object], str]:
        request = self.request_payload("import_preview")
        request["overwrite"] = overwrite
        status, payload = self.post(url, request)
        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        token = result.get("preview_token")
        self.assertIsInstance(token, str)
        assert isinstance(token, str)
        return request, token

    def test_import_preview_is_available_without_write_and_does_not_mutate(self) -> None:
        url = self.start(allow_write=False)

        status, payload = self.post(url, self.request_payload("import_preview"))

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(result["would_create"], ["note/alpha.md", "note/beta.md"])
        self.assertIsInstance(result["preview_token"], str)
        self.assertFalse(result["written"])
        self.assertFalse((self.root / "note").exists())

    def test_browser_payload_cannot_grant_import_write_authority(self) -> None:
        url = self.start(allow_write=False)
        request = self.request_payload("import_write")
        request["allow_write"] = True
        request["preview_token"] = "opaque"

        status, payload = self.post(url, request)

        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "WriteCapabilityDisabled")
        self.assertFalse((self.root / "note").exists())

    def test_write_enabled_process_commits_exact_reviewed_import(self) -> None:
        url = self.start(allow_write=True)
        request, token = self.preview(url)
        request["capability"] = "import_write"
        request["preview_token"] = token

        status, payload = self.post(url, request)

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

    def test_changed_source_after_preview_fails_without_partial_writes(self) -> None:
        url = self.start(allow_write=True)
        request, token = self.preview(url)
        self.source.write_text("slug,title\nalpha,Changed\nbeta,Beta\n", encoding="utf-8")
        request["capability"] = "import_write"
        request["preview_token"] = token

        status, _payload = self.post(url, request)

        self.assertEqual(status, 400)
        self.assertFalse((self.root / "note" / "alpha.md").exists())
        self.assertFalse((self.root / "note" / "beta.md").exists())

    def test_changed_overwrite_destination_after_preview_fails_without_partial_writes(self) -> None:
        note_dir = self.root / "note"
        note_dir.mkdir()
        alpha = note_dir / "alpha.md"
        alpha.write_text("---\ntype: Note\ntitle: Old\n---\n", encoding="utf-8")
        url = self.start(allow_write=True)
        request, token = self.preview(url, overwrite=True)
        newer = "---\ntype: Note\ntitle: Newer\n---\n"
        alpha.write_text(newer, encoding="utf-8")
        request["capability"] = "import_write"
        request["preview_token"] = token

        status, _payload = self.post(url, request)

        self.assertEqual(status, 400)
        self.assertEqual(alpha.read_text(encoding="utf-8"), newer)
        self.assertFalse((note_dir / "beta.md").exists())

    def test_import_write_requires_reviewed_preview_token(self) -> None:
        url = self.start(allow_write=True)

        status, payload = self.post(url, self.request_payload("import_write"))

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "ValueError")
        self.assertIn("preview_token", str(payload["message"]))
        self.assertFalse((self.root / "note").exists())

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
