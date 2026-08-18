"""Task runner for the RxGrowth IQ workspace.

Replaces the Makefile in ``docs/BRIEF.md``. ``make`` is unavailable on the target
platform, and adding a task-runner dependency to save a hundred lines is a poor trade
for a repository whose whole thesis is auditability. Each task is a subprocess
invocation with an explicit command line, so ``uv run lint`` shows you exactly what ran.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

API_HOST = os.environ.get("RXIQ_API_HOST", "127.0.0.1")
API_PORT = os.environ.get("RXIQ_API_PORT", "8000")
WEB_DIR = ROOT / "apps" / "web"


def _run(*command: str, cwd: Path | None = None) -> int:
    """Run a command, echoing it first so the task is reproducible by hand."""
    print(f"$ {' '.join(command)}", flush=True)
    try:
        return subprocess.call(command, cwd=cwd or ROOT)
    except FileNotFoundError:
        print(f"error: {command[0]!r} not found on PATH", file=sys.stderr)
        return 127


def _npm() -> str | None:
    """Locate npm, which is ``npm.cmd`` on Windows."""
    return shutil.which("npm") or shutil.which("npm.cmd")


def _api_command() -> list[str]:
    """Build the uvicorn invocation shared by ``api`` and ``dev``."""
    return [
        "uvicorn",
        "rxiq.api.main:app",
        "--reload",
        "--host",
        API_HOST,
        "--port",
        API_PORT,
    ]


# ---------------------------------------------------------------------------
# Quality gates
# ---------------------------------------------------------------------------


def lint() -> int:
    """Lint Python and, if present, the web app."""
    code = _run("ruff", "check", ".")
    code |= _run("ruff", "format", "--check", ".")
    npm = _npm()
    if npm and (WEB_DIR / "node_modules").exists():
        code |= _run(npm, "run", "lint", cwd=WEB_DIR)
    return code


def fmt() -> int:
    """Auto-format Python."""
    code = _run("ruff", "format", ".")
    code |= _run("ruff", "check", "--fix", ".")
    return code


def typecheck() -> int:
    """Type-check Python and the web app."""
    code = _run("mypy")
    npm = _npm()
    if npm and (WEB_DIR / "node_modules").exists():
        code |= _run(npm, "run", "typecheck", cwd=WEB_DIR)
    return code


def test() -> int:
    """Run the Python test suite with coverage."""
    return _run("pytest", "--cov", "--cov-report=term-missing")


def guard() -> int:
    """Run the real-data scanner against the diff with origin/main.

    Mirrors the Data Guard CI job so a violation is caught before the push, not after.
    See docs/compliance.md section 1.
    """
    scanner = ROOT / "scripts" / "check_no_real_data.py"
    if not scanner.exists():
        print("error: scripts/check_no_real_data.py is missing -- see issue #4", file=sys.stderr)
        return 2
    return _run(sys.executable, str(scanner), "--base", "origin/main", "--head", "HEAD")


def check() -> int:
    """Run every gate CI runs. Use before pushing."""
    failures = []
    for name, task in (("guard", guard), ("lint", lint), ("typecheck", typecheck), ("test", test)):
        print(f"\n=== {name} ===", flush=True)
        if task() != 0:
            failures.append(name)
    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {', '.join(failures)}")
        return 1
    print("All gates passed.")
    return 0


# ---------------------------------------------------------------------------
# Servers
# ---------------------------------------------------------------------------


def api() -> int:
    """Start the FastAPI service with reload."""
    return _run(*_api_command())


def web() -> int:
    """Start the Next.js dev server."""
    npm = _npm()
    if npm is None:
        print("error: npm not found on PATH", file=sys.stderr)
        return 127
    if not (WEB_DIR / "node_modules").exists():
        print("Installing web dependencies (first run)...", flush=True)
        if _run(npm, "install", cwd=WEB_DIR) != 0:
            return 1
    return _run(npm, "run", "dev", cwd=WEB_DIR)


def dev() -> int:
    """Start the API and the web app together.

    Both are long-running, so they are spawned as siblings and torn down together on
    Ctrl-C. Output interleaves; for a clean single-service log use ``uv run api`` or
    ``uv run web`` in separate terminals.
    """
    npm = _npm()
    if npm is not None and not (WEB_DIR / "node_modules").exists():
        print("Installing web dependencies (first run)...", flush=True)
        _run(npm, "install", cwd=WEB_DIR)

    procs: list[subprocess.Popen[bytes]] = []
    commands: list[tuple[str, list[str], Path]] = [
        ("api", _api_command(), ROOT),
    ]
    if npm is not None:
        commands.append(("web", [npm, "run", "dev"], WEB_DIR))

    try:
        for name, command, cwd in commands:
            print(f"$ [{name}] {' '.join(command)}", flush=True)
            procs.append(subprocess.Popen(command, cwd=cwd))
        print(
            f"\n  API  http://{API_HOST}:{API_PORT}\n"
            f"  Docs http://{API_HOST}:{API_PORT}/docs\n"
            f"  Web  http://localhost:3000\n\n"
            "Ctrl-C to stop both.\n",
            flush=True,
        )
        # Poll rather than signal.pause(), which does not exist on Windows.
        while procs:
            time.sleep(0.5)
            for proc in list(procs):
                code = proc.poll()
                if code is not None:
                    procs.remove(proc)
                    if code != 0:
                        print(f"a service exited with code {code}; shutting down", file=sys.stderr)
                        return code
        return 0
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
        return 0
    finally:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(check())
