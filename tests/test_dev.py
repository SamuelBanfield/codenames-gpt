"""Launcher tests use isolated local files and fake processes, without API calls."""

from contextlib import redirect_stderr, redirect_stdout
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
        path = self.backend / ".env"
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-placeholder"}, clear=True), patch("dev.getpass.getpass") as prompt:
            config = dev.configure_backend(path)
            self.assertEqual(config["WEBSOCKET_PORT"], "8000")
            self.assertNotIn("OPENAI_API_KEY", config)
        prompt.assert_not_called()
        self.assertFalse(path.exists())

    def test_prompt_saves_ignored_configuration_preserving_settings_without_printing_key(self):
        from dotenv import dotenv_values
        path = self.backend / ".env"
        path.write_text("GPT_MODEL=configured-model\nGUESS_DELAY=2\n")
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), patch("dev.getpass.getpass", return_value="test-only-placeholder"), redirect_stdout(output), redirect_stderr(output):
            config = dev.configure_backend(path)
        saved = dotenv_values(path)
        self.assertEqual(saved["GPT_MODEL"], "configured-model")
        self.assertEqual(saved["GUESS_DELAY"], "2")
        self.assertEqual(saved["OPENAI_API_KEY"], "test-only-placeholder")
        self.assertEqual(config["GPT_MODEL"], "configured-model")
        self.assertNotIn("test-only-placeholder", json.dumps(config))
        self.assertNotIn("test-only-placeholder", output.getvalue())

    def test_invalid_configuration_does_not_echo_its_content(self):
        path = self.backend / ".env"
        path.write_text("WEBSOCKET_PORT=test-only-placeholder\n")
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(dev.argparse.ArgumentTypeError) as error:
            dev.configure_backend(path)
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
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-placeholder"}), \
             patch("dev.start_process", side_effect=[backend, frontend]) as start, \
             patch("dev.wait_for_servers"), \
             patch("dev.process_failure", side_effect=KeyboardInterrupt), \
             patch("dev.stop_process") as stop, redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                dev.run_servers(self.root, self.python, self.next, "node", {}, 8000, 3000, False)
        self.assertEqual(stop.call_args_list, [call(frontend), call(backend)])
        self.assertEqual(start.call_args_list[0].args[2]["OPENAI_API_KEY"], "test-only-placeholder")
        self.assertNotIn("OPENAI_API_KEY", start.call_args_list[1].args[2])
        self.assertEqual(start.call_args_list[1].args[2]["NEXT_PUBLIC_WEBSOCKET_URL"], "ws://127.0.0.1:8000")
        for invocation in start.call_args_list:
            self.assertNotIn("test-only-placeholder", invocation.args[0])

    def test_failure_to_start_frontend_stops_the_already_started_backend(self):
        backend = Mock()
        with patch("dev.start_process", side_effect=[backend, OSError("cannot launch")]), \
             patch("dev.stop_process") as stop:
            with self.assertRaises(OSError):
                dev.run_servers(self.root, self.python, self.next, "node", {}, 8000, 3000, False)
        stop.assert_called_once_with(backend)

    def test_unexpected_service_exit_stops_its_sibling(self):
        backend, frontend = Mock(), Mock()
        backend.poll.return_value = 1
        frontend.poll.return_value = None
        with patch("dev.start_process", side_effect=[backend, frontend]), \
             patch("dev.wait_for_servers"), patch("dev.stop_process") as stop, redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(dev.StartupError, "Backend exited"):
                dev.run_servers(self.root, self.python, self.next, "node", {}, 8000, 3000, False)
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


    def test_dotenv_is_used_and_environment_and_cli_take_precedence(self):
        path = self.backend / ".env"
        path.write_text("OPENAI_API_KEY=file-only-placeholder\nWEBSOCKET_PORT=8123\nGPT_MODEL=file-model\nGUESS_DELAY=2\n")
        with patch.dict(os.environ, {"GPT_MODEL": "environment-model"}, clear=True), patch("dev.getpass.getpass") as prompt:
            config = dev.configure_backend(path, backend_port=9001)
        prompt.assert_not_called()
        self.assertEqual(config, {"WEBSOCKET_PORT": "9001", "GPT_MODEL": "environment-model", "GUESS_DELAY": "2"})
        self.assertNotIn("file-only-placeholder", json.dumps(config))

    def test_empty_environment_key_does_not_silently_fall_back_to_dotenv(self):
        path = self.backend / ".env"
        path.write_text("OPENAI_API_KEY=file-only-placeholder\n")
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True), patch("dev.getpass.getpass") as prompt:
            with self.assertRaises(dev.StartupError):
                dev.configure_backend(path)
        prompt.assert_not_called()

    def test_backend_configuration_runs_in_managed_python_and_returns_only_public_settings(self):
        public = {"WEBSOCKET_PORT": "8000", "GPT_MODEL": "gpt-4o", "GUESS_DELAY": "1"}
        with patch("dev.subprocess.run", return_value=Mock(returncode=0, stdout=json.dumps(public))) as run:
            self.assertEqual(dev.prepare_backend(self.root, self.python, 9001), public)
        command = run.call_args.args[0]
        self.assertEqual(command[0], str(self.python))
        self.assertEqual(command[-2:], [str(self.backend / ".env"), "9001"])
        self.assertEqual(run.call_args.kwargs["cwd"], self.root)

    def test_setup_does_not_pass_api_key_to_dependency_installers(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-placeholder"}), patch("dev.subprocess.run") as run:
            dev.setup_command(["installer"], self.root)
        self.assertNotIn("OPENAI_API_KEY", run.call_args.kwargs["env"])

    def test_configuration_failure_does_not_start_servers(self):
        with patch("dev.prerequisites", return_value=("node", "npm", "v24.15.0")), \
             patch("dev.check_port"), \
             patch("dev.ensure_dependencies", return_value=(self.python, self.next)), \
             patch("dev.prepare_backend", side_effect=dev.StartupError("configuration failed")), \
             patch("dev.run_servers") as servers, redirect_stderr(io.StringIO()):
            self.assertEqual(dev.main(["--no-browser"]), 1)
        servers.assert_not_called()


if __name__ == "__main__":
    unittest.main()
