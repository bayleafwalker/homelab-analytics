from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Protocol

# Suffix of in-flight filesystem writes. Readers that walk the landing tree
# (backups) skip these: a payload is only visible under its final name once
# fully written.
PARTIAL_WRITE_SUFFIX = ".partial"


class BlobStore(Protocol):
    def write_bytes(self, relative_path: str, content: bytes) -> str:
        ...

    def read_bytes(self, locator: str) -> bytes:
        ...


class FilesystemBlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bytes(self, relative_path: str, content: bytes) -> str:
        destination = self.root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging = destination.with_name(
            f".{destination.name}.{uuid.uuid4().hex}{PARTIAL_WRITE_SUFFIX}"
        )
        try:
            staging.write_bytes(content)
            os.replace(staging, destination)
        except BaseException:
            staging.unlink(missing_ok=True)
            raise
        return str(destination)

    def read_bytes(self, locator: str) -> bytes:
        return Path(locator).read_bytes()


class InMemoryBlobStore:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    def write_bytes(self, relative_path: str, content: bytes) -> str:
        locator = f"memory://{relative_path}"
        self._objects[locator] = content
        return locator

    def read_bytes(self, locator: str) -> bytes:
        return self._objects[locator]
