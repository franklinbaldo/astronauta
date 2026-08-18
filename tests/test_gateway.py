from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from astronauta.gateway import concept, concepts, diagnostics, graph, summary


class GatewayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "people").mkdir()
        (self.root / "tasks").mkdir()
        (self.root / "tasks" / "alpha.md").write_text(
            """---
type: Task
title: Alpha
status: open
---
# Alpha

Owner: [Ada](../people/ada.md)

Missing: [Ghost](../people/ghost.md)
""",
            encoding="utf-8",
        )
        (self.root / "people" / "ada.md").write_text(
            """---
type: Person
title: Ada
---
# Ada

Owns [Alpha](../tasks/alpha.md).
""",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_uses_authored_type_instead_of_folder_inference(self) -> None:
        rows = concepts(self.root)
        self.assertEqual([row["type"] for row in rows], ["Person", "Task"])
        self.assertNotIn("tasks", {row["type"] for row in rows})
        self.assertNotIn("people", {row["type"] for row in rows})

    def test_exact_type_filter_is_deterministic(self) -> None:
        rows = concepts(self.root, concept_type="Task")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["path"], "tasks/alpha.md")
        self.assertEqual(rows[0]["frontmatter"]["status"], "open")

    def test_detail_preserves_forward_reverse_and_broken_links(self) -> None:
        rows = concepts(self.root)
        alpha_id = next(row["id"] for row in rows if row["path"] == "tasks/alpha.md")
        ada_id = next(row["id"] for row in rows if row["path"] == "people/ada.md")

        alpha = concept(self.root, alpha_id)
        self.assertIsNotNone(alpha)
        assert alpha is not None
        self.assertTrue(any(item["target_id"] == ada_id for item in alpha["outgoing_links"]))
        self.assertTrue(any(item["target_id"] is None for item in alpha["outgoing_links"]))
        self.assertTrue(any(item["source_id"] == ada_id for item in alpha["incoming_links"]))

    def test_graph_does_not_promote_broken_links_to_nodes(self) -> None:
        projection = graph(self.root)
        node_ids = {item["id"] for item in projection["nodes"]}
        self.assertEqual(len(node_ids), 2)
        self.assertEqual(len(projection["edges"]), 2)
        self.assertEqual(len(projection["unresolved"]), 1)

    def test_every_call_reads_current_filesystem_state(self) -> None:
        before = summary(self.root)
        (self.root / "tasks" / "beta.md").write_text(
            """---
type: Task
title: Beta
---
# Beta
""",
            encoding="utf-8",
        )
        after = summary(self.root)
        self.assertEqual(after["total_concepts"], before["total_concepts"] + 1)
        self.assertEqual(after["concepts_by_type"]["Task"], 2)

    def test_parser_diagnostics_are_exposed_without_reclassification(self) -> None:
        findings = diagnostics(self.root)
        broken = [item for item in findings if item["code"] == "OKF101"]
        self.assertEqual(len(broken), 1)
        self.assertEqual(broken[0]["severity"], "warning")
        self.assertEqual(broken[0]["path"], "tasks/alpha.md")


if __name__ == "__main__":
    unittest.main()
