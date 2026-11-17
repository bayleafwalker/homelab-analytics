#!/usr/bin/env python3
"""Verify and materialize the locked Noble font and Fontconfig inputs."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tools/dev-browser-assets.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def verify_file(path: Path, expected: str, label: str) -> bool:
    return path.is_file() and sha256(path) == expected


def ensure_checkout_directory(path: Path) -> None:
    relative = path.relative_to(ROOT)
    current = ROOT
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise SystemExit(f"checkout-owned browser asset path contains a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise SystemExit(f"checkout-owned browser asset path is not a directory: {current}")
        current.mkdir(exist_ok=True)


def ensure_checkout_file(path: Path) -> None:
    relative = path.relative_to(ROOT)
    current = ROOT
    for component in relative.parts[:-1]:
        current = current / component
        if current.is_symlink() or not current.is_dir():
            raise SystemExit(f"checkout-owned browser asset path is not a real directory: {current}")
    if path.is_symlink():
        raise SystemExit(f"checkout-owned browser asset file is a symlink: {path}")
    if path.exists() and not path.is_file():
        raise SystemExit(f"checkout-owned browser asset path is not a regular file: {path}")


def verify_checkout_file(path: Path, expected: str) -> bool:
    try:
        ensure_checkout_file(path)
    except SystemExit:
        return False
    return verify_file(path, expected, str(path))


def source_rule_from(directories: tuple[Path, ...], rule: dict) -> Path:
    for directory in directories:
        candidate = directory / rule["name"]
        if verify_file(candidate, rule["sha256"], rule["name"]):
            return candidate
    raise SystemExit(f"pinned Fontconfig rule is missing or changed: {rule['name']}")


def system_matches(data: dict) -> bool:
    ignored = set(data["generated_metadata"])
    for entry in data["fonts"]:
        if entry["path"] in ignored:
            continue
        if not verify_file(Path("/usr/share/fonts") / entry["path"], entry["sha256"], entry["path"]):
            return False
    if not verify_file(Path("/etc/fonts/fonts.conf"), data["base_config_sha256"], "base fonts.conf"):
        return False
    for rule in data["rules"]:
        if not verify_file(Path("/etc/fonts/conf.d") / rule["name"], rule["sha256"], rule["name"]):
            return False
    return True


def materialize_sources(
    fonts_source: Path, config_source: Path, rule_directories: tuple[Path, ...], data: dict
) -> None:
    if not verify_file(config_source, data["base_config_sha256"], "base fonts.conf"):
        raise SystemExit("pinned base Fontconfig config is missing or changed")

    fonts_target = ROOT / ".tooling/playwright-fonts"
    config_target = ROOT / ".tooling/playwright-fontconfig"
    rules_target = config_target / "conf.d"
    cache_target = ROOT / ".tooling/fontconfig-cache"
    for directory in (fonts_target, rules_target, cache_target):
        ensure_checkout_directory(directory)

    ignored = set(data["generated_metadata"])
    for entry in data["fonts"]:
        relative = Path(entry["path"])
        if relative.as_posix() in ignored:
            continue
        source = fonts_source / relative
        if not verify_file(source, entry["sha256"], entry["path"]):
            raise SystemExit(f"pinned font asset is missing or changed: {entry['path']}")
        destination = fonts_target / relative
        ensure_checkout_directory(destination.parent)
        ensure_checkout_file(destination)
        shutil.copyfile(source, destination)
        if not verify_checkout_file(destination, entry["sha256"]):
            raise SystemExit(f"could not materialize verified font asset: {entry['path']}")

    for rule in data["rules"]:
        source = source_rule_from(rule_directories, rule)
        destination = rules_target / rule["name"]
        ensure_checkout_file(destination)
        shutil.copyfile(source, destination)
        if not verify_checkout_file(destination, rule["sha256"]):
            raise SystemExit(f"could not materialize verified Fontconfig rule: {rule['name']}")

    config = config_source.read_text()
    font_dir = str(fonts_target)
    config = re.sub(r"\s*<dir>/usr/share/fonts</dir>", f"\n\t<dir>{font_dir}</dir>", config, count=1)
    config = re.sub(r"\s*<dir>/usr/local/share/fonts</dir>", "", config, count=1)
    config = re.sub(r'\s*<dir prefix="xdg">fonts</dir>', "", config, count=1)
    config = re.sub(r"\s*<dir>~/.fonts</dir>", "", config, count=1)
    config = config.replace(
        '<include ignore_missing="yes">conf.d</include>',
        f'<include ignore_missing="no">{rules_target}</include>',
    )
    config = re.sub(r"\s*<cachedir>/var/cache/fontconfig</cachedir>", f"\n\t<cachedir>{cache_target}</cachedir>", config, count=1)
    config = re.sub(r'\s*<cachedir prefix="xdg">fontconfig</cachedir>', "", config, count=1)
    config = re.sub(r"\s*<cachedir>~/.fontconfig</cachedir>", "", config, count=1)
    if "<dir>/usr/share/fonts</dir>" in config or "<cachedir>/var/cache/fontconfig</cachedir>" in config:
        raise SystemExit("could not isolate Fontconfig font and cache paths")
    config_path = config_target / "fonts.conf"
    ensure_checkout_file(config_path)
    config_path.write_text(config)
    provenance = {
        "manifest_sha256": sha256(MANIFEST),
        "base_config_sha256": data["base_config_sha256"],
        "materialized_config_sha256": sha256(config_path),
        "font_payload_count": len(data["fonts"]) - len(ignored),
        "font_rule_count": len(data["rules"]),
    }
    marker = config_target / ".hla-assets-provenance.json"
    ensure_checkout_file(marker)
    marker.write_text(json.dumps(provenance, sort_keys=True) + "\n")


def materialize(assets: Path) -> None:
    materialize_sources(
        assets / "usr/share/fonts",
        assets / "etc/fonts/fonts.conf",
        (assets / "usr/share/fontconfig/conf.avail", assets / "etc/fonts/conf.avail"),
        manifest(),
    )


def materialize_system() -> None:
    data = manifest()
    if not system_matches(data):
        raise SystemExit("host font and Fontconfig files do not match the locked baseline")
    materialize_sources(
        Path("/usr/share/fonts"),
        Path("/etc/fonts/fonts.conf"),
        (Path("/etc/fonts/conf.d"),),
        data,
    )


def materialized_matches() -> bool:
    data = manifest()
    fonts_target = ROOT / ".tooling/playwright-fonts"
    config_target = ROOT / ".tooling/playwright-fontconfig"
    provenance_path = config_target / ".hla-assets-provenance.json"
    config_path = config_target / "fonts.conf"
    try:
        ensure_checkout_file(provenance_path)
        ensure_checkout_file(config_path)
    except SystemExit:
        return False
    if not provenance_path.is_file() or not config_path.is_file():
        return False
    try:
        provenance = json.loads(provenance_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    if provenance.get("manifest_sha256") != sha256(MANIFEST):
        return False
    if provenance.get("materialized_config_sha256") != sha256(config_path):
        return False
    ignored = set(data["generated_metadata"])
    for entry in data["fonts"]:
        if entry["path"] in ignored:
            continue
        if not verify_checkout_file(fonts_target / entry["path"], entry["sha256"]):
            return False
    for rule in data["rules"]:
        if not verify_checkout_file(config_target / "conf.d" / rule["name"], rule["sha256"]):
            return False
    return True


if __name__ == "__main__":
    spec = manifest()
    if len(sys.argv) == 2 and sys.argv[1] == "system-matches":
        raise SystemExit(0 if system_matches(spec) else 1)
    if len(sys.argv) == 2 and sys.argv[1] == "materialized-matches":
        raise SystemExit(0 if materialized_matches() else 1)
    if len(sys.argv) == 2 and sys.argv[1] == "materialize-system":
        materialize_system()
        raise SystemExit(0)
    if len(sys.argv) == 3 and sys.argv[1] == "materialize":
        materialize(Path(sys.argv[2]))
        raise SystemExit(0)
    raise SystemExit(
        "usage: dev-browser-assets.py system-matches | materialized-matches | "
        "materialize-system | materialize RUNTIME_ASSETS_DIR"
    )
