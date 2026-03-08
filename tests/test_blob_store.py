from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from packages.storage.blob import FilesystemBlobStore, InMemoryBlobStore


class FilesystemBlobStoreTests(unittest.TestCase):
    def test_blob_store_writes_and_reads_bytes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = FilesystemBlobStore(Path(temp_dir))

            locator = store.write_bytes("2026/03/test.txt", b"hello")

            self.assertTrue(Path(locator).is_file())
            self.assertEqual(b"hello", store.read_bytes(locator))

    def test_in_memory_blob_store_writes_and_reads_bytes(self) -> None:
        store = InMemoryBlobStore()

        locator = store.write_bytes("2026/03/test.txt", b"hello")

        self.assertEqual("memory://2026/03/test.txt", locator)
        self.assertEqual(b"hello", store.read_bytes(locator))


if __name__ == "__main__":
    unittest.main()
