from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

from typer.testing import CliRunner

from astronauta import cli, runtime


class CliRuntimeTests(unittest.TestCase):
    def test_target_cli_keeps_write_authority_process_owned(self) -> None:
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(cli, "serve_admin") as serve:
                result = runner.invoke(
                    cli.app,
                    [str(root), "--write", "--port", "4567"],
                )

        self.assertEqual(result.exit_code, 0, result.output)
        serve.assert_called_once_with(
            root.resolve(),
            write=True,
            port=4567,
            spec_template=None,
            on_ready=ANY,
        )

    def test_runtime_wires_ephemeral_gateway_into_astro_child(self) -> None:
        root = Path("/tmp/bundle").resolve()
        server = MagicMock()
        server.server_address = ("127.0.0.1", 48123)
        process = MagicMock()
        process.poll.return_value = 0
        process.wait.return_value = 0
        entry = Path("/tmp/project/dist/server/entry.mjs")
        ready = MagicMock()

        with (
            patch.object(runtime, "GatewayServer", return_value=server) as gateway_server,
            patch.object(runtime, "_resolve_web_entry", return_value=entry),
            patch.object(runtime, "_node_executable", return_value="/usr/bin/node"),
            patch.object(runtime, "_wait_for_web") as wait_for_web,
            patch.object(runtime.subprocess, "Popen", return_value=process) as popen,
        ):
            runtime.serve_admin(
                root,
                write=False,
                port=4321,
                spec_template="docs/types/{slug}.md",
                on_ready=ready,
            )

        gateway_server.assert_called_once_with(
            ("127.0.0.1", 0),
            root,
            spec_template="docs/types/{slug}.md",
            allow_write=False,
        )
        server.serve_forever.assert_called_once_with()
        wait_for_web.assert_called_once_with(process, "127.0.0.1", 4321)
        ready.assert_called_once_with()
        args, kwargs = popen.call_args
        self.assertEqual(args[0], ["/usr/bin/node", str(entry)])
        self.assertEqual(kwargs["cwd"], Path("/tmp/project"))
        self.assertEqual(
            kwargs["env"]["ASTRONAUTA_GATEWAY_URL"],
            "http://127.0.0.1:48123/gateway",
        )
        self.assertEqual(kwargs["env"]["HOST"], "127.0.0.1")
        self.assertEqual(kwargs["env"]["PORT"], "4321")
        process.terminate.assert_not_called()
        server.shutdown.assert_called_once_with()
        server.server_close.assert_called_once_with()

    def test_interrupt_terminates_astro_and_closes_gateway(self) -> None:
        root = Path("/tmp/bundle").resolve()
        server = MagicMock()
        server.server_address = ("127.0.0.1", 48123)
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = [KeyboardInterrupt(), 0]

        with (
            patch.object(runtime, "GatewayServer", return_value=server),
            patch.object(
                runtime,
                "_resolve_web_entry",
                return_value=Path("/tmp/project/dist/server/entry.mjs"),
            ),
            patch.object(runtime, "_node_executable", return_value="/usr/bin/node"),
            patch.object(runtime, "_wait_for_web"),
            patch.object(runtime.subprocess, "Popen", return_value=process),
        ):
            runtime.serve_admin(root, write=True, port=4321, spec_template=None)

        process.terminate.assert_called_once_with()
        process.wait.assert_called_with(timeout=5.0)
        process.kill.assert_not_called()
        server.shutdown.assert_called_once_with()
        server.server_close.assert_called_once_with()

    def test_force_kills_child_that_ignores_termination(self) -> None:
        process = MagicMock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("node", 5.0), 0]

        runtime._stop_child(process)

        process.terminate.assert_called_once_with()
        process.kill.assert_called_once_with()
        self.assertEqual(process.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
