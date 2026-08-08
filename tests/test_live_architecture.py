from __future__ import annotations

import unittest
from pathlib import Path

from typer.testing import CliRunner

from astronauta.cli import app


ROOT = Path(__file__).resolve().parents[1]


class LiveArchitectureTests(unittest.TestCase):
    def test_cli_no_longer_exposes_static_generation(self) -> None:
        result = CliRunner().invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("gateway", result.output)
        self.assertNotIn("generate", result.output)
        self.assertNotIn("--out", result.output)

    def test_pages_do_not_import_generated_json_snapshots(self) -> None:
        forbidden = (
            "src/data/",
            "../data/",
            "summary.json",
            "concepts.json",
            "diagnostics.json",
            "graph.json",
        )
        offenders: list[str] = []
        for path in sorted((ROOT / "src" / "pages").rglob("*.astro")):
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_cli_contains_no_folder_type_inference_or_generated_data_writer(self) -> None:
        text = (ROOT / "src" / "astronauta" / "cli.py").read_text(encoding="utf-8")
        self.assertNotIn("output_dir", text)
        self.assertNotIn("src/data", text)
        self.assertNotIn("parts[-2]", text)
        self.assertNotIn("write_text", text)


if __name__ == "__main__":
    unittest.main()
