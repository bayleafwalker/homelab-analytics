from __future__ import annotations

from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


class S3BlobStore:
    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None = None,
        region_name: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        prefix: str = "",
        create_bucket_if_missing: bool = True,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region_name,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(s3={"addressing_style": "path"}),
        )
        if create_bucket_if_missing:
            self._ensure_bucket(region_name)

    def write_bytes(self, relative_path: str, content: bytes) -> str:
        key = self._build_key(relative_path)
        self._client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return f"s3://{self.bucket}/{key}"

    def read_bytes(self, locator: str) -> bytes:
        bucket, key = self._resolve_locator(locator)
        response = self._client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def _build_key(self, relative_path: str) -> str:
        normalized = relative_path.lstrip("/")
        if not self.prefix:
            return normalized
        return f"{self.prefix}/{normalized}"

    def _resolve_locator(self, locator: str) -> tuple[str, str]:
        if locator.startswith("s3://"):
            parsed = urlparse(locator)
            return parsed.netloc, parsed.path.lstrip("/")
        return self.bucket, self._build_key(locator)

    def _ensure_bucket(self, region_name: str) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return
        except ClientError:
            pass

        try:
            if region_name == "us-east-1":
                self._client.create_bucket(Bucket=self.bucket)
                return

            self._client.create_bucket(
                Bucket=self.bucket,
                CreateBucketConfiguration={"LocationConstraint": region_name},
            )
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                raise
