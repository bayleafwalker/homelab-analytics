from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_entrypoints(root: Path) -> None:
    (root / "tools").mkdir(parents=True)
    for name in (
        "dev-env.sh",
        "dev-setup.sh",
        "dev-check.sh",
        "dev-check-runtime.sh",
        "dev-check-runtime-probe.py",
        "dev-browser.sh",
        "dev-browser-assets.py",
        "dev-playwright-executable.cjs",
        "dev-playwright-preflight.cjs",
        "dev-web-ui-test.sh",
        "dev-smoke-process.sh",
        "dev-smoke-backend-stub.py",
        "dev-smoke.sh",
    ):
        shutil.copy2(REPO_ROOT / "tools" / name, root / "tools" / name)


def _add_node_provenance(node_dir: Path) -> None:
    (node_dir.parent / ".hla-node-provenance").write_text(
        "archive=node-v20.20.1-linux-x64.tar.gz "
        "sha256=6362e50804cdcc110592201f67beda93bcd702fdcbe1c42840a50d590e3af0ce\n"
    )


def _setup_fixture(root: Path) -> Path:
    _copy_entrypoints(root)
    (root / "uv.lock").touch()
    frontend = root / "apps/web/frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text('{"name":"fixture"}\n')
    (frontend / "package-lock.json").write_text(
        '{"name":"fixture","lockfileVersion":3,"requires":true,'
        '"packages":{"":{"name":"fixture"}}}\n'
    )
    return frontend


def _write_fake_owned_runtime(root: Path) -> None:
    node_home = root / ".tooling/node-v20.20.1-linux-x64"
    node_dir = node_home / "bin"
    node_dir.mkdir(parents=True)
    _add_node_provenance(node_dir)
    node = node_dir / "node"
    node.write_text(
        "#!/bin/sh\n"
        "if [ \"$1\" = --version ]; then echo v20.20.1; "
        "elif [ \"$2\" = --version ]; then \"$@\"; else exit 1; fi\n"
    )
    npm = node_dir / "npm"
    npm.write_text("#!/bin/sh\n[ \"$1\" = --version ] && echo 10.8.2\n")
    node.chmod(0o755)
    npm.chmod(0o755)


def _write_fake_project_python(root: Path) -> None:
    python = root / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)


def _run(
    script: str, root: Path, *, path: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(root / "tools" / script)],
        cwd=root,
        env={**os.environ, "PATH": path or os.environ.get("PATH", "/usr/bin:/bin")},
        text=True,
        capture_output=True,
        check=False,
    )


def test_setup_requires_committed_frontend_lock_before_downloads(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    (tmp_path / "uv.lock").touch()
    frontend = tmp_path / "apps/web/frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text('{"name":"fixture"}\n')
    result = _run("dev-setup.sh", tmp_path)
    assert result.returncode != 0
    assert "package-lock.json is missing" in result.stderr
    assert not (tmp_path / ".tooling").exists()


def test_setup_refuses_symlinked_tooling_before_bootstrap(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    (tmp_path / "uv.lock").touch()
    frontend = tmp_path / "apps/web/frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text('{"name":"fixture"}\n')
    (frontend / "package-lock.json").write_text(
        '{"name":"fixture","lockfileVersion":3,"requires":true,"packages":{"":{"name":"fixture"}}}\n'
    )
    external_tooling = tmp_path / "external-tooling"
    external_tooling.mkdir()
    (tmp_path / ".tooling").symlink_to(external_tooling, target_is_directory=True)

    result = _run("dev-setup.sh", tmp_path)
    assert result.returncode != 0
    assert "tooling directory contains a symlink" in result.stderr
    assert list(external_tooling.iterdir()) == []


def test_setup_refuses_foreign_python_environment_before_uv(tmp_path: Path) -> None:
    _setup_fixture(tmp_path)
    foreign = tmp_path / "foreign-venv"
    foreign.mkdir()
    sentinel = foreign / "sentinel"
    sentinel.write_text("unchanged\n")
    (tmp_path / ".venv").symlink_to(foreign, target_is_directory=True)

    result = _run("dev-setup.sh", tmp_path)
    assert result.returncode != 0
    assert "Python environment contains a symlink" in result.stderr
    assert sentinel.read_text() == "unchanged\n"
    assert not (foreign / "pyvenv.cfg").exists()


def test_setup_refuses_foreign_frontend_dependency_and_build_targets(tmp_path: Path) -> None:
    for target_name in ("node_modules", ".next"):
        checkout = tmp_path / target_name
        checkout.mkdir()
        frontend = _setup_fixture(checkout)
        foreign = checkout / f"foreign-{target_name}"
        foreign.mkdir()
        sentinel = foreign / "sentinel"
        sentinel.write_text("unchanged\n")
        (frontend / target_name).symlink_to(foreign, target_is_directory=True)

        result = _run("dev-setup.sh", checkout)
        assert result.returncode != 0
        expected_label = "frontend dependencies" if target_name == "node_modules" else "Next.js build output"
        assert f"{expected_label} contains a symlink" in result.stderr
        assert sentinel.read_text() == "unchanged\n"


def test_setup_rejects_ambient_package_manager_target_overrides(tmp_path: Path) -> None:
    _setup_fixture(tmp_path)
    for variable, value, message in (
        ("UV_PROJECT_ENVIRONMENT", str(tmp_path / "foreign-venv"), "UV_PROJECT_ENVIRONMENT redirects"),
        ("npm_config_prefix", str(tmp_path / "foreign-npm"), "npm_config_prefix redirects"),
    ):
        result = subprocess.run(
            [shutil.which("bash") or "/bin/bash", str(tmp_path / "tools/dev-setup.sh")],
            cwd=tmp_path,
            env={**os.environ, variable: value},
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode != 0
        assert message in result.stderr
        assert not (tmp_path / "foreign-venv/pyvenv.cfg").exists()
        assert not (tmp_path / "foreign-npm/node_modules").exists()


def test_check_fails_actionably_without_owned_node_even_if_ambient_node_exists(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    ambient = tmp_path / "ambient"
    ambient.mkdir()
    (ambient / "node").write_text("#!/bin/sh\necho v20.20.1\n")
    (ambient / "node").chmod(0o755)
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").write_text("#!/bin/sh\nexit 0\n")
    (tmp_path / ".venv/bin/python").chmod(0o755)

    result = _run(
        "dev-check.sh", tmp_path, path=f"{ambient}:{os.environ.get('PATH', '/usr/bin:/bin')}"
    )
    assert result.returncode != 0
    assert "owned pinned Node runtime directory is missing" in result.stderr
    assert "make dev-setup" in result.stderr


def test_check_rejects_wrong_or_unusable_owned_node(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    node_dir = tmp_path / ".tooling/node-v20.20.1-linux-x64/bin"
    node_dir.mkdir(parents=True)
    _add_node_provenance(node_dir)
    npm = node_dir / "npm"
    npm.write_text("#!/bin/sh\nexit 0\n")
    npm.chmod(0o755)
    node = node_dir / "node"
    node.write_text("#!/bin/sh\necho v18.19.0\n")
    node.chmod(0o755)
    (tmp_path / ".venv/bin").mkdir(parents=True)
    python = tmp_path / ".venv/bin/python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)

    result = _run("dev-check.sh", tmp_path)
    assert result.returncode != 0
    assert "expected pinned Node.js v20.20.1" in result.stderr

    node.write_text("#!/bin/sh\nexit 126\n")
    result = _run("dev-check.sh", tmp_path)
    assert result.returncode != 0
    assert "pinned Node.js at" in result.stderr
    assert "cannot run" in result.stderr

    node.write_text(
        "#!/bin/sh\nif [ \"$1\" = --version ]; then echo v20.20.1; else \"$@\"; fi\n"
    )
    npm.write_text("#!/bin/sh\nexit 1\n")
    result = _run("dev-check.sh", tmp_path)
    assert result.returncode != 0
    assert "pinned npm cannot run" in result.stderr


def test_check_requires_installed_frontend_toolchain(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    node_dir = tmp_path / ".tooling/node-v20.20.1-linux-x64/bin"
    node_dir.mkdir(parents=True)
    _add_node_provenance(node_dir)
    (node_dir / "node").write_text("#!/bin/sh\nif [ \"$1\" = --version ]; then echo v20.20.1; else exit 0; fi\n")
    (node_dir / "npm").write_text("#!/bin/sh\nexit 0\n")
    (node_dir / "node").chmod(0o755)
    (node_dir / "npm").chmod(0o755)
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    result = _run("dev-check.sh", tmp_path)
    assert result.returncode != 0
    assert "frontend dependencies are missing" in result.stderr


def test_check_rejects_missing_esbuild_native_executable_fixture(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    node_dir = tmp_path / ".tooling/node-v20.20.1-linux-x64/bin"
    node_dir.mkdir(parents=True)
    _add_node_provenance(node_dir)
    node = node_dir / "node"
    node.write_text(
        "#!/bin/sh\nif [ \"$1\" = --version ]; then echo v20.20.1; else exit 0; fi\n"
    )
    npm = node_dir / "npm"
    npm.write_text("#!/bin/sh\nexit 1\n")
    node.chmod(0o755)
    npm.chmod(0o755)
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o755)
    (tmp_path / "apps/web/frontend/node_modules/.bin").mkdir(parents=True)
    tsc = tmp_path / "apps/web/frontend/node_modules/.bin/tsc"
    tsc.touch()
    tsc.chmod(0o755)

    result = _run("dev-check.sh", tmp_path)
    assert result.returncode != 0
    assert "esbuild native executable" in result.stderr


def test_check_reports_unusable_duckdb_loader_environment(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    node_dir = tmp_path / ".tooling/node-v20.20.1-linux-x64/bin"
    node_dir.mkdir(parents=True)
    _add_node_provenance(node_dir)
    node = node_dir / "node"
    node.write_text(
        "#!/bin/sh\nif [ \"$1\" = --version ]; then echo v20.20.1; else exit 0; fi\n"
    )
    npm = node_dir / "npm"
    npm.write_text("#!/bin/sh\nexit 0\n")
    node.chmod(0o755)
    npm.chmod(0o755)
    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text(
        "#!/bin/sh\ncase \"$2\" in *'sys.version_info'*) exit 0;; *'import duckdb'*) exit 1;; esac\n"
    )
    python.chmod(0o755)

    result = _run("dev-check.sh", tmp_path)
    assert result.returncode != 0
    assert "cannot load the locked DuckDB runtime" in result.stderr


def test_check_rejects_unverified_or_symlinked_node_runtime(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    node_home = tmp_path / ".tooling/node-v20.20.1-linux-x64"
    node_dir = node_home / "bin"
    node_dir.mkdir(parents=True)
    (node_dir / "node").write_text("#!/bin/sh\necho v20.20.1\n")
    (node_dir / "npm").write_text("#!/bin/sh\nexit 0\n")
    (node_dir / "node").chmod(0o755)
    (node_dir / "npm").chmod(0o755)
    result = _run("dev-check.sh", tmp_path)
    assert result.returncode != 0
    assert "no checksum-verified install provenance" in result.stderr

    external_home = tmp_path / "external-node-runtime"
    node_home.rename(external_home)
    node_home.symlink_to(external_home, target_is_directory=True)
    result = _run("dev-check.sh", tmp_path)
    assert result.returncode != 0
    assert "missing or symlinked" in result.stderr


def _start_smoke_group(
    tmp_path: Path, *, ignore_child_term: bool
) -> tuple[subprocess.Popen[bytes], int]:
    child_pid_file = tmp_path / f"child-{time.monotonic_ns()}.pid"
    child_ready_file = tmp_path / f"child-{time.monotonic_ns()}.ready"
    child_term = (
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)"
        if ignore_child_term
        else "signal.signal(signal.SIGTERM, signal.SIG_DFL)"
    )
    child = (
        "import pathlib, signal, time; "
        f"{child_term}; pathlib.Path({str(child_ready_file)!r}).touch(); time.sleep(120)"
    )
    leader = (
        "import pathlib, signal, subprocess, sys, time; "
        f"child = subprocess.Popen([sys.executable, '-c', {child!r}]); "
        f"ready = pathlib.Path({str(child_ready_file)!r}); "
        "deadline = time.monotonic() + 5; "
        "exec('while not ready.exists() and time.monotonic() < deadline: time.sleep(0.01)'); "
        f"pathlib.Path({str(child_pid_file)!r}).write_text(str(child.pid)); "
        "signal.signal(signal.SIGTERM, signal.SIG_DFL); time.sleep(120)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", leader],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 5
    while not child_pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert child_pid_file.exists(), "smoke process group did not create its child"
    return process, int(child_pid_file.read_text())


def _process_is_running(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().split()[2]
    except FileNotFoundError:
        return False
    return state not in {"Z", "X"}


def _stop_smoke_group(
    root: Path, pgid: int, *, checks: int = 20
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            shutil.which("bash") or "/bin/bash",
            "-c",
            'source "$1"; dev_stop_process_group "$2" "$3" "$3" 0.05',
            "smoke-cleanup-test",
            str(root / "tools/dev-smoke-process.sh"),
            str(pgid),
            str(checks),
        ],
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )


def test_smoke_cleanup_settles_term_responsive_real_child_group(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    leader, child_pid = _start_smoke_group(tmp_path, ignore_child_term=False)
    result = _stop_smoke_group(tmp_path, leader.pid)
    leader.wait(timeout=2)
    assert result.returncode == 0, result.stderr
    assert not _process_is_running(child_pid)


def test_smoke_cleanup_kills_term_ignoring_real_descendant(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    leader, child_pid = _start_smoke_group(tmp_path, ignore_child_term=True)
    started = time.monotonic()
    result = _stop_smoke_group(tmp_path, leader.pid, checks=4)
    leader.wait(timeout=2)
    assert result.returncode == 0, result.stderr
    assert time.monotonic() - started >= 0.1
    assert not _process_is_running(child_pid)


def test_smoke_cleanup_uncertain_settlement_is_nonpassing(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_ps = fake_bin / "ps"
    fake_ps.write_text("#!/bin/sh\nprintf '424242 S\\n'\n")
    fake_ps.chmod(0o755)
    result = subprocess.run(
        [
            shutil.which("bash") or "/bin/bash",
            "-c",
            'source "$1"; kill() { return 1; }; dev_stop_process_group 424242 1 1 0',
            "smoke-cleanup-failure-test",
            str(tmp_path / "tools/dev-smoke-process.sh"),
        ],
        env={**os.environ, "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}"},
        text=True,
        capture_output=True,
        timeout=3,
        check=False,
    )
    assert result.returncode != 0
    assert "did not settle after bounded SIGTERM/SIGKILL waits" in result.stderr


def test_smoke_term_cancellation_settles_owned_child_group(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    for caught_signal, expected_status in ((signal.SIGINT, 130), (signal.SIGTERM, 143)):
        leader, child_pid = _start_smoke_group(tmp_path, ignore_child_term=True)
        log = tmp_path / f"smoke-{caught_signal}.log"
        manager = subprocess.Popen(
            [
                shutil.which("bash") or "/bin/bash",
                "-c",
                'source "$1"; server_pid="$2"; LOG="$3"; '
                "dev_smoke_install_traps; while :; do sleep 1; done",
                "smoke-cancellation-test",
                str(tmp_path / "tools/dev-smoke-process.sh"),
                str(leader.pid),
                str(log),
            ],
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.05)
        manager.send_signal(caught_signal)
        _, stderr = manager.communicate(timeout=5)
        leader.wait(timeout=2)
        assert manager.returncode == expected_status, stderr.decode()
        assert not _process_is_running(child_pid)


def test_smoke_cancellation_during_build_settles_build_and_backend_groups(
    tmp_path: Path,
) -> None:
    _copy_entrypoints(tmp_path)
    backend, backend_child = _start_smoke_group(tmp_path, ignore_child_term=False)
    smoke_home = tmp_path / "smoke-home"
    smoke_tmp = tmp_path / "smoke-tmp"
    smoke_home.mkdir()
    smoke_tmp.mkdir()
    build_pid_file = tmp_path / "build.pid"
    manager_script = (
        'source "$1"; backend_pid="$2"; '
        'dev_smoke_install_traps; '
        'dev_smoke_launch "$3" "$4" "$5" http://127.0.0.1:1 sleep 30 & '
        'build_pid=$!; printf "%s\\n" "$build_pid" > "$6"; wait "$build_pid"'
    )
    manager = subprocess.Popen(
        [
            shutil.which("bash") or "/bin/bash",
            "-c",
            manager_script,
            "smoke-build-cancellation-test",
            str(tmp_path / "tools/dev-smoke-process.sh"),
            str(backend.pid),
            str(tmp_path),
            str(smoke_home),
            str(smoke_tmp),
            str(build_pid_file),
        ],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    deadline = time.monotonic() + 5
    while not build_pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert build_pid_file.exists(), "smoke manager did not start its build process group"
    build_pid = int(build_pid_file.read_text())
    deadline = time.monotonic() + 5
    while not _process_is_running(build_pid) and time.monotonic() < deadline:
        time.sleep(0.01)

    started = time.monotonic()
    manager.send_signal(signal.SIGTERM)
    _, stderr = manager.communicate(timeout=8)
    assert manager.returncode == 143, stderr.decode()
    assert time.monotonic() - started < 5
    assert not _process_is_running(build_pid)
    assert not _process_is_running(backend_child)
    backend.wait(timeout=2)


def test_smoke_refuses_foreign_node_modules_and_next_before_build(tmp_path: Path) -> None:
    for target_name in ("node_modules", ".next"):
        checkout = tmp_path / target_name
        checkout.mkdir()
        _copy_entrypoints(checkout)
        _write_fake_owned_runtime(checkout)
        _write_fake_project_python(checkout)
        frontend = checkout / "apps/web/frontend"
        frontend.mkdir(parents=True, exist_ok=True)
        foreign = checkout / f"foreign-{target_name}"
        foreign.mkdir()
        sentinel = foreign / "sentinel"
        sentinel.write_text("unchanged\n")
        if target_name == "node_modules":
            (foreign / ".bin").mkdir()
            (foreign / ".bin/next").write_text("#!/bin/sh\nexit 0\n")
            (foreign / ".bin/next").chmod(0o755)
        else:
            (frontend / "node_modules/.bin").mkdir(parents=True)
            (frontend / "node_modules/.bin/next").write_text("#!/bin/sh\nexit 0\n")
            (frontend / "node_modules/.bin/next").chmod(0o755)
        (frontend / target_name).symlink_to(foreign, target_is_directory=True)

        result = _run("dev-smoke.sh", checkout)
        assert result.returncode != 0
        expected = "frontend dependencies" if target_name == "node_modules" else "Next.js build output"
        assert f"{expected} contains a symlink" in result.stderr
        assert sentinel.read_text() == "unchanged\n"


def test_smoke_environment_ignores_ambient_backend_and_identity(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    ambient_requests: list[str] = []

    class AmbientHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            ambient_requests.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:
            return

    ambient_server = ThreadingHTTPServer(("127.0.0.1", 0), AmbientHandler)
    ambient_thread = threading.Thread(target=ambient_server.serve_forever, daemon=True)
    ambient_thread.start()
    ambient_url = f"http://127.0.0.1:{ambient_server.server_port}"
    stub_endpoint = tmp_path / "stub-endpoint"
    stub = subprocess.Popen(
        [
            sys.executable,
            str(tmp_path / "tools/dev-smoke-backend-stub.py"),
            str(stub_endpoint),
        ],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 5
    while not stub_endpoint.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert stub_endpoint.exists(), "synthetic backend stub did not bind loopback"
    stub_url = f"http://127.0.0.1:{stub_endpoint.read_text().strip()}"
    capture = tmp_path / "capture.py"
    capture.write_text(
        "import os, sys\nfrom urllib.error import HTTPError\nfrom urllib.request import urlopen\n"
        "assert os.environ['HOMELAB_ANALYTICS_API_BASE_URL'] == sys.argv[1]\n"
        "assert os.environ['HOMELAB_ANALYTICS_IDENTITY_MODE'] == 'disabled'\n"
        "assert 'HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET' not in os.environ\n"
        "try:\n"
        "    urlopen(os.environ['HOMELAB_ANALYTICS_API_BASE_URL'] + '/probe', timeout=2)\n"
        "except HTTPError as error:\n"
        "    assert error.code == 503\n"
        "else:\n"
        "    raise AssertionError('synthetic backend stub must not supply product data')\n"
        "print(sys.argv[2])\n"
    )
    ambient = {
        **os.environ,
        "HOMELAB_ANALYTICS_API_BASE_URL": ambient_url,
        "HOMELAB_ANALYTICS_IDENTITY_MODE": "oidc",
        "HOMELAB_ANALYTICS_OIDC_CLIENT_SECRET": "ambient-test-value",
    }
    try:
        for phase in ("build", "runtime"):
            result = subprocess.run(
                [
                    shutil.which("bash") or "/bin/bash",
                    "-c",
                    'source "$1"; dev_smoke_env "$2" "$3" "$4" python "$5" "$4" "$6"',
                    "smoke-environment-test",
                    str(tmp_path / "tools/dev-smoke-process.sh"),
                    str(tmp_path / "home"),
                    str(tmp_path / "tmp"),
                    stub_url,
                    str(capture),
                    phase,
                ],
                env=ambient,
                text=True,
                capture_output=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            assert result.stdout.strip() == phase
        assert ambient_requests == [], "smoke process contacted ambient backend instead of stub"
    finally:
        ambient_server.shutdown()
        ambient_server.server_close()
        ambient_thread.join(timeout=2)
        _stop_smoke_group(tmp_path, stub.pid)
        stub.wait(timeout=2)


def test_local_testclient_probe_times_out_before_suite_with_actionable_error(
    tmp_path: Path,
) -> None:
    _copy_entrypoints(tmp_path)
    fake_python = tmp_path / "stalled-python"
    fake_python.write_text("#!/bin/sh\nexec sleep 30\n")
    fake_python.chmod(0o755)
    result = subprocess.run(
        [
            shutil.which("bash") or "/bin/bash",
            "-c",
            'source "$1"; dev_run_local_test_runtime_probe "$2" "$3" 0.2',
            "local-testclient-probe-test",
            str(tmp_path / "tools/dev-check-runtime.sh"),
            str(fake_python),
            str(tmp_path / "tools/dev-check-runtime-probe.py"),
        ],
        text=True,
        capture_output=True,
        timeout=3,
        check=False,
    )
    assert result.returncode != 0
    assert "local FastAPI/TestClient runtime probe failed or timed out within 0.2s" in result.stderr
