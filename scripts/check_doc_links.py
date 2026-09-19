#!/usr/bin/env python3
"""Check relative markdown links (inline and reference-style) resolve to existing files/dirs."""
import os
import re
import subprocess
import sys

INLINE_RE = re.compile(r'\[[^\]]*\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+"[^"]*")?\s*\)')
REF_RE = re.compile(r'^\s*\[[^\]]+\]:\s*(<[^>]*>|\S+)(?:\s+"[^"]*")?\s*$')
FENCE_RE = re.compile(r'^\s*(```|~~~)')


def list_md_files():
    out = subprocess.run(['git', 'ls-files', '*.md'], capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f.strip()]


def strip_angle(target):
    target = target.strip()
    if target.startswith('<') and target.endswith('>'):
        target = target[1:-1]
    return target


def is_skippable(target):
    if not target:
        return True
    if target.startswith('#'):
        return True
    if target.startswith('mailto:'):
        return True
    if target.startswith('//'):
        return True
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', target):
        return True
    return False


def path_part(target):
    # strip fragment
    target = target.split('#', 1)[0]
    return target.strip()


def check_file(path):
    missing = []
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    in_fence = False
    fence_marker = None
    base_dir = os.path.dirname(path)

    for lineno, line in enumerate(lines, start=1):
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif marker == fence_marker:
                in_fence = False
                fence_marker = None
            continue
        if in_fence:
            continue

        targets = []
        for im in INLINE_RE.finditer(line):
            targets.append(im.group(1))
        rm = REF_RE.match(line)
        if rm:
            targets.append(rm.group(1))

        for raw in targets:
            target = strip_angle(raw)
            if is_skippable(target):
                continue
            pp = path_part(target)
            if not pp:
                continue
            if is_skippable(pp):
                continue
            resolved = os.path.normpath(os.path.join(base_dir, pp))
            if not os.path.exists(resolved):
                missing.append((lineno, target))
    return missing


def main():
    files = list_md_files()
    total = 0
    for path in files:
        if not os.path.exists(path):
            continue
        missing = check_file(path)
        for lineno, target in missing:
            print(f"{path}:{lineno}: {target}")
            total += 1
    print(f"total: {total}")
    return 1 if total > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
