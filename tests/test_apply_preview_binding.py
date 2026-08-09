from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from astronauta.mutations import dispatch_mutation


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
        self.sql = 'UPDATE "Note" SET status = \'done\' WHERE __okf_concept_id = \'note\''

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def dispatch(self, capability: str, **payload: object) -> dict[str, object]:
        return dispatch_mutation(
            self.root,
            capability,
            {"capability": capability, **payload},
            allow_write=True,
            spec_template=None,
        )

    def preview_token(self) -> str:
        result = self.dispatch("apply_preview", sql=self.sql)
        token = result.get("preview_token")
        self.assertIsInstance(token, str)
        assert isinstance(token, str)
        self.assertTrue(token.startswith("okf-apply-preview-v1-sha256:"))
        return token

    def test_commit_requires_preview_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "preview_token"):
            self.dispatch("apply_write", sql=self.sql)
        self.assertIn("status: todo", self.note.read_text(encoding="utf-8"))

    def test_wrong_preview_token_fails_closed(self) -> None:
        result = self.dispatch(
            "apply_write",
            sql=self.sql,
            preview_token="okf-apply-preview-v1-sha256:" + "0" * 64,
        )

        self.assertFalse(result["succeeded"])
        self.assertFalse(result["written"])
        self.assertEqual(
            result["error"],
            "apply candidate no longer matches the reviewed preview",
        )
        self.assertIn("status: todo", self.note.read_text(encoding="utf-8"))

    def test_exact_reviewed_preview_commits(self) -> None:
        token = self.preview_token()

        result = self.dispatch("apply_write", sql=self.sql, preview_token=token)

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

        result = self.dispatch("apply_write", sql=self.sql, preview_token=token)

        self.assertFalse(result["succeeded"])
        self.assertFalse(result["written"])
        self.assertEqual(
            result["error"],
            "apply candidate no longer matches the reviewed preview",
        )
        self.assertIn("status: todo", self.note.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
