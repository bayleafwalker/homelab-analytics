from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fixture(root: Path, *, wrong_font: bool = False) -> tuple[Path, Path]:
    tools = root / "tools"
    tools.mkdir(parents=True)
    helper = tools / "dev-browser-assets.py"
    shutil.copy2(REPO_ROOT / "tools/dev-browser-assets.py", helper)

    font = b"locked font payload"
    rule = b"<fontconfig><match/></fontconfig>\n"
    base_config = (
        b'<fontconfig><dir>/usr/share/fonts</dir>'
        b'<dir>/usr/local/share/fonts</dir><dir prefix="xdg">fonts</dir><dir>~/.fonts</dir>'
        b'<include ignore_missing="yes">conf.d</include>'
        b'<cachedir>/var/cache/fontconfig</cachedir>'
        b'<cachedir prefix="xdg">fontconfig</cachedir><cachedir>~/.fontconfig</cachedir></fontconfig>'
    )
    data = {
        "base_config_sha256": _sha(base_config),
        "generated_metadata": ["X11/Test/fonts.dir"],
        "fonts": [
            {"path": "truetype/test/Fixture.ttf", "sha256": _sha(font)},
            {"path": "X11/Test/fonts.dir", "sha256": _sha(b"generated index")},
        ],
        "rules": [{"name": "50-test.conf", "sha256": _sha(rule)}],
    }
    (tools / "dev-browser-assets.json").write_text(json.dumps(data))
    assets = root / "source-assets"
    (assets / "usr/share/fonts/truetype/test").mkdir(parents=True)
    (assets / "usr/share/fontconfig/conf.avail").mkdir(parents=True)
    (assets / "etc/fonts").mkdir(parents=True)
    (assets / "usr/share/fonts/truetype/test/Fixture.ttf").write_bytes(b"wrong" if wrong_font else font)
    (assets / "usr/share/fontconfig/conf.avail/50-test.conf").write_bytes(rule)
    (assets / "etc/fonts/fonts.conf").write_bytes(base_config)
    return helper, assets


def test_materializer_copies_hash_checked_assets_and_isolates_fontconfig(tmp_path: Path) -> None:
    helper, assets = _fixture(tmp_path)
    result = subprocess.run(
        [sys.executable, str(helper), "materialize", str(assets)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    font = tmp_path / ".tooling/playwright-fonts/truetype/test/Fixture.ttf"
    rule = tmp_path / ".tooling/playwright-fontconfig/conf.d/50-test.conf"
    config = (tmp_path / ".tooling/playwright-fontconfig/fonts.conf").read_text()
    assert font.read_bytes() == b"locked font payload"
    assert rule.read_bytes() == b"<fontconfig><match/></fontconfig>\n"
    assert not (tmp_path / ".tooling/playwright-fonts/X11/Test/fonts.dir").exists()
    assert str(tmp_path / ".tooling/playwright-fonts") in config
    assert str(tmp_path / ".tooling/playwright-fontconfig/conf.d") in config
    assert str(tmp_path / ".tooling/fontconfig-cache") in config
    assert "/usr/share/fonts" not in config
    assert "/var/cache/fontconfig" not in config

    verified = subprocess.run(
        [sys.executable, str(helper), "materialized-matches"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert verified.returncode == 0, verified.stderr


def test_materializer_refuses_changed_font_source(tmp_path: Path) -> None:
    helper, assets = _fixture(tmp_path, wrong_font=True)
    result = subprocess.run(
        [sys.executable, str(helper), "materialize", str(assets)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "pinned font asset is missing or changed" in result.stderr
    assert not (tmp_path / ".tooling/playwright-fonts/truetype/test/Fixture.ttf").exists()


def test_materializer_refuses_foreign_font_output_before_copy(tmp_path: Path) -> None:
    helper, assets = _fixture(tmp_path)
    foreign = tmp_path / "foreign-fonts"
    foreign.mkdir()
    sentinel = foreign / "sentinel"
    sentinel.write_text("untouched\n")
    tooling = tmp_path / ".tooling"
    tooling.mkdir()
    (tooling / "playwright-fonts").symlink_to(foreign, target_is_directory=True)
    result = subprocess.run(
        [sys.executable, str(helper), "materialize", str(assets)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert "contains a symlink" in result.stderr
    assert sentinel.read_text() == "untouched\n"
    assert list(foreign.iterdir()) == [sentinel]
