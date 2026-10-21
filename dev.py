"""One-command local development: python dev.py (Python 3.12+, Node.js 20.19+)."""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import venv
import webbrowser


ROOT = Path(__file__).resolve().parent
IS_WINDOWS = os.name == "nt"


class StartupError(Exception):
    pass


def port_number(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("Port must be an integer") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("Port must be between 1 and 65535")
    return port


def prerequisites():
    if sys.version_info < (3, 12):
        raise StartupError("Use Python 3.12 or newer to run this launcher.")
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if IS_WINDOWS else "npm")
    if not node or not npm:
        raise StartupError("Install Node.js 20.19+ (or 22.12+) and ensure node/npm are on PATH.")
    result = subprocess.run([node, "--version"], capture_output=True, text=True, check=True)
    version = result.stdout.strip()
    try:
        major, minor, _ = map(int, version.lstrip("v").split("."))
    except ValueError:
        raise StartupError("Could not determine the Node.js version.") from None
    if not (major == 20 and minor >= 19 or major == 22 and minor >= 12 or major > 22):
        raise StartupError("Use Node.js 20.19+ (or 22.12+).")
    return node, npm, version


def configure_backend(path, backend_port=None):
    """Run using the managed venv; return public launch settings, never the key."""
    from dotenv import dotenv_values, set_key
    from backend.codenames.options import load_settings

    values = dict(dotenv_values(path, interpolate=False))
    values.update(os.environ)
    values["WEBSOCKET_PORT"] = str(port_number(
        backend_port if backend_port is not None else values.get("WEBSOCKET_PORT", "8000"),
    ))
    values.setdefault("GUESS_DELAY", "1")
    configured_key = values.get("OPENAI_API_KEY")
    if not isinstance(configured_key, str) or not configured_key.strip():
        if "OPENAI_API_KEY" in os.environ:
            raise StartupError("OPENAI_API_KEY is empty; unset it to use backend/.env.")
        print("No OpenAI API key configured. It will be saved in ignored backend/.env.", file=sys.stderr)
        try:
            key = getpass.getpass("OpenAI API key: ").strip()
        except EOFError:
            raise StartupError("Set OPENAI_API_KEY or add it to backend/.env.") from None
        if not key:
            raise StartupError("An OpenAI API key is required for AI players.")
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.close(descriptor)
        set_key(path, "OPENAI_API_KEY", key, quote_mode="always")
        values["OPENAI_API_KEY"] = key
        print("Saved local configuration; you will not be prompted next time.", file=sys.stderr)
    settings = load_settings(env_file=None, environ=values)
    return {"WEBSOCKET_PORT": str(settings.websocket_port), "GPT_MODEL": settings.gpt_model,
            "GUESS_DELAY": str(settings.guess_delay)}


def prepare_backend(root, python, backend_port):
    # The launcher itself stays stdlib-only. Dotenv/configuration runs after
    # dependency setup, in the managed venv, with only public settings on stdout.
    script = """import json, sys
from pathlib import Path
import dev
try:
    config = dev.configure_backend(Path(sys.argv[1]), int(sys.argv[2]) if sys.argv[2] else None)
except (dev.StartupError, OSError, ValueError, dev.argparse.ArgumentTypeError) as error:
    print(f'Cannot configure backend: {error}', file=sys.stderr)
    sys.exit(1)
print(json.dumps(config))
"""
    result = subprocess.run([str(python), "-c", script, str(root / "backend/.env"),
                             str(backend_port) if backend_port is not None else ""],
                            cwd=root, stdout=subprocess.PIPE, text=True)
    if result.returncode:
        raise StartupError("Backend configuration failed; see its message above.")
    return json.loads(result.stdout)


def fingerprint(paths, version):
    digest = hashlib.sha256(version.encode())
    for path in paths:
        digest.update(path.read_bytes())
    return digest.hexdigest()


def installed(stamp, expected, executable):
    return executable.exists() and stamp.exists() and stamp.read_text(encoding="utf-8").strip() == expected


def setup_command(command, cwd):
    environment = os.environ.copy()
    environment.pop("OPENAI_API_KEY", None)
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def ensure_dependencies(root, node, npm, node_version):
    backend, frontend = root / "backend", root / "codenames-gpt-ui"
    environment = backend / ".venv"
    python = environment / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")
    if not python.exists():
        print("Creating the backend virtual environment…", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    requirements = backend / "requirements.txt"
    stamp = environment / ".dev-requirements.sha256"
    expected = fingerprint([requirements], f"{sys.version_info.major}.{sys.version_info.minor}")
    if not installed(stamp, expected, python):
        print("Installing backend dependencies…", flush=True)
        setup_command([str(python), "-m", "pip", "install", "-r", str(requirements)], backend)
        stamp.write_text(expected, encoding="utf-8")

    next_cli = frontend / "node_modules/next/dist/bin/next"
    stamp = frontend / "node_modules/.dev-packages.sha256"
    expected = fingerprint([frontend / "package.json", frontend / "package-lock.json"], node_version)
    if not installed(stamp, expected, next_cli):
        print("Installing frontend dependencies…", flush=True)
        # Windows .cmd entry points need cmd.exe; the application itself runs
        # directly through node so its process tree can be stopped reliably.
        command = [npm, "ci"]
        if IS_WINDOWS:
            command = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", npm, "ci"]
        setup_command(command, frontend)
        stamp.write_text(expected, encoding="utf-8")
    return python, next_cli


def check_port(port):
    with socket.socket() as listener:
        try:
            listener.bind(("127.0.0.1", port))
        except OSError:
            raise StartupError(f"Port {port} is unavailable. Stop the existing server or choose another port.") from None


def start_process(command, cwd, environment):
    options = {"cwd": cwd, "env": environment}
    if IS_WINDOWS:
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def stop_process(process):
    if IS_WINDOWS:
        # Kill the complete tree, including Next.js's separate server worker.
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if IS_WINDOWS:
            process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)


def process_failure(processes):
    for name, process in processes:
        code = process.poll()
        if code is not None:
            raise StartupError(f"{name} exited with code {code}. See its output above.")


def wait_for_servers(processes, ports, timeout=90):
    deadline = time.monotonic() + timeout
    pending = set(ports)
    while pending:
        process_failure(processes)
        for port in list(pending):
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    pending.remove(port)
            except OSError:
                pass
        if pending:
            if time.monotonic() >= deadline:
                raise StartupError("Servers did not start in time. See their output above.")
            time.sleep(0.2)


def run_servers(root, python, next_cli, node, config, backend_port, ui_port, open_browser):
    backend_environment = os.environ.copy()
    backend_environment.update(config)
    backend_environment.update({
        "HOST": "127.0.0.1", "WEBSOCKET_PORT": str(backend_port),
        "PYTHONUNBUFFERED": "1",
    })
    frontend_environment = os.environ.copy()
    frontend_environment.pop("OPENAI_API_KEY", None)
    frontend_environment["NEXT_PUBLIC_WEBSOCKET_URL"] = f"ws://127.0.0.1:{backend_port}"
    processes = []
    try:
        processes.append(("Backend", start_process([str(python), "run.py"], root / "backend", backend_environment)))
        processes.append(("Frontend", start_process(
            [node, str(next_cli), "dev", "--hostname", "127.0.0.1", "--port", str(ui_port)],
            root / "codenames-gpt-ui", frontend_environment,
        )))
        wait_for_servers(processes, [backend_port, ui_port])
        url = f"http://localhost:{ui_port}/codenames"
        print(f"\nGame ready: {url}\nPress Ctrl+C to stop both servers.\n", flush=True)
        if open_browser:
            webbrowser.open(url)
        while True:
            process_failure(processes)
            time.sleep(0.5)
    finally:
        signals = [signal.SIGINT] + ([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])
        handlers = {value: signal.getsignal(value) for value in signals}
        for value in signals:
            signal.signal(value, signal.SIG_IGN)
        try:
            for _, process in reversed(processes):
                stop_process(process)
        finally:
            for value, handler in handlers.items():
                signal.signal(value, handler)


def main(argv=None):
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, signal.default_int_handler)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=port_number, default=3000, help="Frontend port (default: 3000)")
    parser.add_argument("--backend-port", type=port_number, help="Override the backend port (default: configuration or 8000)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser automatically")
    args = parser.parse_args(argv)
    try:
        node, npm, version = prerequisites()
        check_port(args.port)
        python, next_cli = ensure_dependencies(ROOT, node, npm, version)
        config = prepare_backend(ROOT, python, args.backend_port)
        backend_port = port_number(config["WEBSOCKET_PORT"])
        if args.port == backend_port:
            raise StartupError("The backend and frontend must use different ports.")
        check_port(backend_port)
        run_servers(ROOT, python, next_cli, node, config, backend_port, args.port, not args.no_browser)
    except KeyboardInterrupt:
        print("\nStopped both servers.")
        return 0
    except (StartupError, OSError, subprocess.SubprocessError, argparse.ArgumentTypeError) as error:
        print(f"Could not start: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
