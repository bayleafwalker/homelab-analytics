import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from botocore.exceptions import ClientError

from packages.storage.blob import FilesystemBlobStore, InMemoryBlobStore
from packages.storage.s3_blob import S3BlobStore


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


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.created_buckets: list[tuple[str, dict[str, object] | None]] = []
        self.existing_buckets: set[str] = set()

    def head_bucket(self, *, Bucket: str) -> None:
        if Bucket not in self.existing_buckets:
            raise ClientError(
                {
                    "Error": {
                        "Code": "404",
                        "Message": f"Bucket {Bucket} was not found.",
                    }
                },
                "HeadBucket",
            )

    def create_bucket(
        self,
        *,
        Bucket: str,
        CreateBucketConfiguration: dict[str, object] | None = None,
    ) -> None:
        self.created_buckets.append((Bucket, CreateBucketConfiguration))
        self.existing_buckets.add(Bucket)

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[(Bucket, Key)] = Body

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, io.BytesIO]:
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}


class S3BlobStoreTests(unittest.TestCase):
    @patch("packages.storage.s3_blob.boto3.client")
    def test_s3_blob_store_writes_and_reads_with_prefix(self, client_factory) -> None:
        fake_client = _FakeS3Client()
        client_factory.return_value = fake_client

        store = S3BlobStore(
            bucket="landing",
            endpoint_url="http://minio.local",
            access_key_id="minio",
            secret_access_key="password",
            prefix="bronze",
        )

        locator = store.write_bytes("account_transactions/2026/03/test.csv", b"hello")

        self.assertEqual(
            "s3://landing/bronze/account_transactions/2026/03/test.csv",
            locator,
        )
        self.assertEqual(
            [("landing", None)],
            fake_client.created_buckets,
        )
        self.assertEqual(b"hello", store.read_bytes(locator))

    @patch("packages.storage.s3_blob.boto3.client")
    def test_s3_blob_store_can_read_relative_locator(self, client_factory) -> None:
        fake_client = _FakeS3Client()
        fake_client.existing_buckets.add("landing")
        fake_client.objects[("landing", "bronze/2026/03/test.txt")] = b"hello"
        client_factory.return_value = fake_client

        store = S3BlobStore(bucket="landing", prefix="bronze")

        self.assertEqual(b"hello", store.read_bytes("2026/03/test.txt"))


if __name__ == "__main__":
    unittest.main()
