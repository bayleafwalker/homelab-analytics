from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _copy_entrypoints(root: Path) -> None:
    (root / "tools").mkdir(parents=True)
    for name in ("dev-env.sh", "dev-setup.sh", "dev-check.sh"):
        shutil.copy2(REPO_ROOT / "tools" / name, root / "tools" / name)


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
    assert "pinned Node.js 20.20.1 is missing" in result.stderr
    assert "make dev-setup" in result.stderr


def test_check_rejects_wrong_or_unusable_owned_node(tmp_path: Path) -> None:
    _copy_entrypoints(tmp_path)
    node_dir = tmp_path / ".tooling/node-v20.20.1-linux-x64/bin"
    node_dir.mkdir(parents=True)
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
