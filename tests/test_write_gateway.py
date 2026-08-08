from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from okf_parser import load_bundle

from astronauta.gateway_http import GatewayServer


class WriteGatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "note.md"
        self.source.write_text(
            """---
type: Note
title: Hello
status: todo
---
Old body
""",
            encoding="utf-8",
        )
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

    def source_digest(self) -> str:
        bundle = load_bundle(self.root)
        row = bundle.concepts.select("source_digest").execute()
        return str(row.iloc[0]["source_digest"])

    def test_body_preview_is_available_without_write_authority(self) -> None:
        url = self.start(allow_write=False)
        before = self.source.read_text(encoding="utf-8")

        status, payload = self.post(
            url,
            {
                "capability": "edit_preview",
                "concept_id": "note",
                "body": "New body\n",
                "expected_source_digest": self.source_digest(),
            },
        )

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertTrue(result["changed"])
        self.assertFalse(result["written"])
        self.assertEqual(self.source.read_text(encoding="utf-8"), before)

    def test_payload_cannot_grant_itself_body_write_authority(self) -> None:
        url = self.start(allow_write=False)
        before = self.source.read_text(encoding="utf-8")

        status, payload = self.post(
            url,
            {
                "capability": "edit_write",
                "concept_id": "note",
                "body": "Escalated body\n",
                "expected_source_digest": self.source_digest(),
                "allow_write": True,
            },
        )

        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "WriteCapabilityDisabled")
        self.assertEqual(self.source.read_text(encoding="utf-8"), before)

    def test_write_enabled_process_commits_body_edit(self) -> None:
        url = self.start(allow_write=True)

        status, payload = self.post(
            url,
            {
                "capability": "edit_write",
                "concept_id": "note",
                "body": "Committed body\n",
                "expected_source_digest": self.source_digest(),
            },
        )

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertTrue(result["written"])
        self.assertIn("Committed body", self.source.read_text(encoding="utf-8"))
        self.assertIn("status: todo", self.source.read_text(encoding="utf-8"))

    def test_apply_preview_is_available_without_write_authority(self) -> None:
        url = self.start(allow_write=False)
        before = self.source.read_text(encoding="utf-8")
        sql = 'UPDATE "Note" SET status = \'done\' WHERE __okf_concept_id = \'note\''

        status, payload = self.post(url, {"capability": "apply_preview", "sql": sql})

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertEqual(result["changed_paths"], ["note.md"])
        self.assertFalse(result["written"])
        self.assertEqual(self.source.read_text(encoding="utf-8"), before)

    def test_payload_cannot_grant_itself_apply_write_authority(self) -> None:
        url = self.start(allow_write=False)
        before = self.source.read_text(encoding="utf-8")
        sql = 'UPDATE "Note" SET status = \'done\' WHERE __okf_concept_id = \'note\''

        status, payload = self.post(
            url,
            {"capability": "apply_write", "sql": sql, "allow_write": True},
        )

        self.assertEqual(status, 403)
        self.assertEqual(payload["error"], "WriteCapabilityDisabled")
        self.assertEqual(self.source.read_text(encoding="utf-8"), before)

    def test_write_enabled_process_commits_duckdb_apply(self) -> None:
        url = self.start(allow_write=True)
        sql = 'UPDATE "Note" SET status = \'done\' WHERE __okf_concept_id = \'note\''

        status, payload = self.post(url, {"capability": "apply_write", "sql": sql})

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertTrue(result["written"])
        self.assertIn("status: done", self.source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
