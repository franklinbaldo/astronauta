from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from astronauta.gateway_http import GatewayServer


class ApplyPreviewBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.note = self.root / "note.md"
        self.note.write_text(
            """---
type: Note
status: todo
---
Body
""",
            encoding="utf-8",
        )
        self.other = self.root / "other.md"
        self.other.write_text(
            """---
type: Other
title: Other
---
Other body
""",
            encoding="utf-8",
        )
        self.server = GatewayServer(("127.0.0.1", 0), self.root, allow_write=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}/gateway"
        self.sql = 'UPDATE "Note" SET status = \'done\' WHERE __okf_concept_id = \'note\''

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def post(self, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        request = Request(
            self.url,
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

    def preview_token(self) -> str:
        status, payload = self.post({"capability": "apply_preview", "sql": self.sql})
        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        token = result.get("preview_token")
        self.assertIsInstance(token, str)
        assert isinstance(token, str)
        self.assertTrue(token.startswith("okf-apply-preview-v1-sha256:"))
        return token

    def test_commit_requires_preview_token(self) -> None:
        status, payload = self.post({"capability": "apply_write", "sql": self.sql})

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "ValueError")
        self.assertIn("preview_token", str(payload["message"]))
        self.assertIn("status: todo", self.note.read_text(encoding="utf-8"))

    def test_wrong_preview_token_fails_closed(self) -> None:
        status, payload = self.post(
            {
                "capability": "apply_write",
                "sql": self.sql,
                "preview_token": "okf-apply-preview-v1-sha256:" + "0" * 64,
            }
        )

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertFalse(result["succeeded"])
        self.assertFalse(result["written"])
        self.assertEqual(
            result["error"],
            "apply candidate no longer matches the reviewed preview",
        )
        self.assertIn("status: todo", self.note.read_text(encoding="utf-8"))

    def test_exact_reviewed_preview_commits(self) -> None:
        token = self.preview_token()

        status, payload = self.post(
            {"capability": "apply_write", "sql": self.sql, "preview_token": token}
        )

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertTrue(result["succeeded"])
        self.assertTrue(result["written"])
        self.assertEqual(result["preview_token"], token)
        self.assertIn("status: done", self.note.read_text(encoding="utf-8"))

    def test_bundle_change_after_preview_fails_closed(self) -> None:
        token = self.preview_token()
        self.other.write_text(
            self.other.read_text(encoding="utf-8") + "External change\n",
            encoding="utf-8",
        )

        status, payload = self.post(
            {"capability": "apply_write", "sql": self.sql, "preview_token": token}
        )

        self.assertEqual(status, 200)
        result = payload["result"]
        self.assertIsInstance(result, dict)
        assert isinstance(result, dict)
        self.assertFalse(result["succeeded"])
        self.assertFalse(result["written"])
        self.assertEqual(
            result["error"],
            "apply candidate no longer matches the reviewed preview",
        )
        self.assertIn("status: todo", self.note.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
