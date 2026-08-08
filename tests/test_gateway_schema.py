from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from astronauta.gateway import schemas


class GatewaySchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "types").mkdir()
        (self.root / "task.md").write_text(
            """---
type: Task
title: Alpha
count: "7"
due: "2026-08-08"
---
# Alpha
""",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_declared_duckdb_types_flow_from_parser_contract(self) -> None:
        (self.root / "types" / "task.schema.sql").write_text(
            """CREATE TABLE "Task" (
    title VARCHAR,
    count BIGINT,
    due DATE
);
COMMENT ON COLUMN "Task".count IS 'Number of executions.';
""",
            encoding="utf-8",
        )
        payload = schemas(self.root, spec_template="types/{slug}.md")
        properties = payload["schemas"]["Task"]["properties"]
        self.assertEqual(properties["count"]["x-okf-duckdb-type"], "BIGINT")
        self.assertEqual(properties["due"]["x-okf-duckdb-type"], "DATE")

    def test_schema_sql_is_not_discovered_without_operator_opt_in(self) -> None:
        (self.root / "types" / "task.schema.sql").write_text(
            "this is deliberately invalid DuckDB SQL",
            encoding="utf-8",
        )
        payload = schemas(self.root)
        self.assertIn("Task", payload["schemas"])
        with self.assertRaises(Exception):
            schemas(self.root, spec_template="types/{slug}.md")


if __name__ == "__main__":
    unittest.main()
