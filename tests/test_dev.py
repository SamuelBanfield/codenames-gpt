"""Launcher tests use isolated local files and fake processes, without API calls."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, call, patch

import dev


class LauncherTests(unittest.TestCase):
    def setUp(self):
        cache = dev.ROOT / ".cache"
        cache.mkdir(exist_ok=True)
        directory = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.backend = self.root / "backend"
        self.frontend = self.root / "codenames-gpt-ui"
        self.backend.mkdir()
        self.frontend.mkdir()
        (self.backend / "requirements.txt").write_text("dependency==1\n")
        (self.frontend / "package.json").write_text("{}")
        (self.frontend / "package-lock.json").write_text("{}")
        self.python = self.backend / ".venv" / ("Scripts/python.exe" if dev.IS_WINDOWS else "bin/python")
        self.next = self.frontend / "node_modules/next/dist/bin/next"
        for executable in (self.python, self.next):
            executable.parent.mkdir(parents=True)
            executable.touch()

    def test_environment_key_is_used_without_saving_or_prompting(self):
        path = self.backend / ".properties.json"
        with patch.dict(os.environ, {"OPENAI_KEY": "test-only-placeholder"}), patch("dev.getpass.getpass") as prompt:
            self.assertEqual(dev.api_key({}, path), "test-only-placeholder")
        prompt.assert_not_called()
        self.assertFalse(path.exists())

    def test_prompt_saves_ignored_configuration_preserving_settings_without_printing_key(self):
        path = self.backend / ".properties.json"
        properties = {"gptModel": "configured-model", "guessDelay": 2}
        output = io.StringIO()
        with patch.dict(os.environ, {"OPENAI_KEY": ""}), patch("dev.getpass.getpass", return_value="test-only-placeholder"), redirect_stdout(output):
            dev.api_key(properties, path)
        saved = json.loads(path.read_text())
        self.assertEqual(saved["gptModel"], "configured-model")
        self.assertEqual(saved["guessDelay"], 2)
        self.assertEqual(saved["openaiKey"], "test-only-placeholder")
        self.assertNotIn("test-only-placeholder", output.getvalue())

    def test_invalid_configuration_does_not_echo_its_content(self):
        path = self.backend / ".properties.json"
        path.write_text('{"openaiKey": "test-only-placeholder"')
        with self.assertRaises(dev.StartupError) as error:
            dev.read_properties(path)
        self.assertNotIn("test-only-placeholder", str(error.exception))

    def test_dependencies_are_cached_and_only_changed_inputs_are_reinstalled(self):
        with patch("dev.setup_command") as install, redirect_stdout(io.StringIO()):
            dev.ensure_dependencies(self.root, "node", "npm", "v24.15.0")
            self.assertEqual(install.call_count, 2)
            dev.ensure_dependencies(self.root, "node", "npm", "v24.15.0")
            self.assertEqual(install.call_count, 2)
            (self.backend / "requirements.txt").write_text("dependency==2\n")
            dev.ensure_dependencies(self.root, "node", "npm", "v24.15.0")
            self.assertEqual(install.call_count, 3)
            self.assertIn("pip", install.call_args.args[0])
            (self.frontend / "package-lock.json").write_text('{"changed": true}')
            dev.ensure_dependencies(self.root, "node", "npm", "v24.15.0")
            self.assertEqual(install.call_count, 4)
            self.assertIn("ci", install.call_args.args[0])

    def test_failed_install_does_not_record_a_successful_cache_stamp(self):
        failure = subprocess.CalledProcessError(1, ["installer"])
        with patch("dev.setup_command", side_effect=failure), redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                dev.ensure_dependencies(self.root, "node", "npm", "v24.15.0")
        self.assertFalse((self.backend / ".venv/.dev-requirements.sha256").exists())
        self.assertFalse((self.frontend / "node_modules/.dev-packages.sha256").exists())

    def test_keyboard_interrupt_stops_both_services_and_key_is_backend_only(self):
        backend, frontend = Mock(), Mock()
        with patch.dict(os.environ, {"OPENAI_KEY": "test-only-placeholder"}), \
             patch("dev.start_process", side_effect=[backend, frontend]) as start, \
             patch("dev.wait_for_servers"), \
             patch("dev.process_failure", side_effect=KeyboardInterrupt), \
             patch("dev.stop_process") as stop, redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                dev.run_servers(self.root, self.python, self.next, "node", {}, "test-only-placeholder", 8000, 3000, False)
        self.assertEqual(stop.call_args_list, [call(frontend), call(backend)])
        self.assertEqual(start.call_args_list[0].args[2]["OPENAI_KEY"], "test-only-placeholder")
        self.assertNotIn("OPENAI_KEY", start.call_args_list[1].args[2])
        self.assertEqual(start.call_args_list[1].args[2]["NEXT_PUBLIC_WEBSOCKET_URL"], "ws://127.0.0.1:8000")
        for invocation in start.call_args_list:
            self.assertNotIn("test-only-placeholder", invocation.args[0])

    def test_failure_to_start_frontend_stops_the_already_started_backend(self):
        backend = Mock()
        with patch("dev.start_process", side_effect=[backend, OSError("cannot launch")]), \
             patch("dev.stop_process") as stop:
            with self.assertRaises(OSError):
                dev.run_servers(self.root, self.python, self.next, "node", {}, "test-only-placeholder", 8000, 3000, False)
        stop.assert_called_once_with(backend)

    def test_unexpected_service_exit_stops_its_sibling(self):
        backend, frontend = Mock(), Mock()
        backend.poll.return_value = 1
        frontend.poll.return_value = None
        with patch("dev.start_process", side_effect=[backend, frontend]), \
             patch("dev.wait_for_servers"), patch("dev.stop_process") as stop, redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(dev.StartupError, "Backend exited"):
                dev.run_servers(self.root, self.python, self.next, "node", {}, "test-only-placeholder", 8000, 3000, False)
        self.assertEqual(stop.call_args_list, [call(frontend), call(backend)])

    def test_windows_cleanup_targets_the_complete_next_process_tree(self):
        process = Mock(pid=1234)
        with patch("dev.IS_WINDOWS", True), patch("dev.subprocess.run") as run:
            dev.stop_process(process)
        self.assertEqual(run.call_args.args[0], ["taskkill", "/PID", "1234", "/T", "/F"])
        process.wait.assert_called_once_with(timeout=5)

    def test_supported_node_versions_are_checked_before_setup(self):
        with patch("dev.shutil.which", return_value="executable"):
            for version in ("v20.19.0", "v22.12.0", "v24.15.0"):
                with patch("dev.subprocess.run", return_value=Mock(stdout=version)):
                    self.assertEqual(dev.prerequisites()[2], version)
            for version in ("v18.20.0", "v20.18.0", "v21.7.0", "v22.11.0"):
                with patch("dev.subprocess.run", return_value=Mock(stdout=version)):
                    with self.assertRaises(dev.StartupError):
                        dev.prerequisites()


if __name__ == "__main__":
    unittest.main()
