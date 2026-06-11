import os
from collections.abc import Iterator
from typing import Any, BinaryIO

import boto3
import botocore
from mypy_boto3_s3.service_resource import (
    Bucket,
    Object,
    ObjectSummary,
    S3ServiceResource,
)


class R2Service:
    def __init__(
        self,
        r2_endpoint_url: str,
        r2_access_key_id: str,
        r2_secret_access_key: str,
        r2_bucket_name: str,
        r2_pub_url: str,
    ) -> None:
        """Initialize an R2 (S3-compatible) resource wrapper.

        Params:
            r2_endpoint_url: R2 endpoint URL (S3-compatible API endpoint).
            r2_access_key_id: Access key ID for authentication.
            r2_secret_access_key: Secret access key for authentication.
            r2_bucket_name: Default bucket name to operate on.
            r2_pub_url: Public base URL used to build public asset URLs.
        """
        self.s3: S3ServiceResource = boto3.resource(
            service_name="s3",
            endpoint_url=r2_endpoint_url,
            aws_access_key_id=r2_access_key_id,
            aws_secret_access_key=r2_secret_access_key,
            region_name="auto",
        )

        self.bucket: Bucket = self.s3.Bucket(str(r2_bucket_name))

        self.r2_endpoint_url = r2_endpoint_url
        self.r2_access_key_id = r2_access_key_id
        self.r2_secret_access_key = r2_secret_access_key
        self.r2_bucket_name = r2_bucket_name
        self.r2_pub_url = r2_pub_url

    def list_objects(self, r2_prefix: str) -> list[ObjectSummary]:
        """List objects under a given prefix.

        Params:
            r2_prefix: Prefix to list (e.g., "folder/").

        Returns:
            List of ObjectSummary for matched objects.
        """
        return list(self.bucket.objects.filter(Prefix=r2_prefix))

    def get_info(self, r2_path: str) -> Object:
        """Get object metadata/handle for a given key.

        Params:
            r2_path: Object key (path).

        Returns:
            Object handle (mypy_boto3_s3 Object) for further operations.
        """
        return self.bucket.Object(r2_path)

    def exists(self, r2_path: str) -> bool:
        """Return True if the object exists (HEAD request), False if not.

        Params:
            r2_path: Object key (path) to check.
        """
        obj = self.bucket.Object(r2_path)
        try:
            obj.load()
            return True
        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                return False
            raise

    def get_public_url(self, r2_path: str) -> str:
        """Build a public URL for an object key, using the configured base.

        Note: `r2_path` must not start with a leading slash.

        Params:
            r2_path: Object key (path) inside the bucket.

        Returns:
            Absolute public URL that can be shared.
        """
        return f"{self.r2_pub_url}/{r2_path}"

    def upload(self, local_path: str, r2_path: str) -> None:
        """Upload a local file to the bucket.

        Params:
            local_path: Absolute or relative local filesystem path to the source file.
            r2_path: Object key (path) in the bucket to upload to.
        """
        self.bucket.upload_file(local_path, r2_path)

    def upload_bytes(self, data: bytes, r2_path: str) -> None:
        """Upload raw bytes to the bucket.

        Used for small files.

        Params:
            data: In-memory bytes to upload as the object body.
            r2_path: Object key (path) in the bucket to upload to.
        """
        self.bucket.put_object(Key=r2_path, Body=data)

    def upload_stream(
        self,
        fileobj: BinaryIO,
        r2_path: str,
        content_type: str | None = None,
        extra_args: dict[str, Any] | None = None,
    ) -> None:
        """Upload from a file-like object (streaming, no temp file).

        Used for large files.

        Params:
            fileobj: File-like object opened in binary mode (supports .read()).
            r2_path: Destination object key (path).
            content_type: Optional MIME type stored with the object.
            extra_args: Optional extra S3 args (e.g., CacheControl, ContentDisposition).
        """
        args = dict(extra_args or {})
        if content_type:
            args["ContentType"] = content_type

        self.bucket.upload_fileobj(fileobj, r2_path, ExtraArgs=args)

    def download(self, local_path: str, r2_path: str) -> None:
        """Download a single object to a local path.

        Params:
            local_path: Destination local filesystem path.
            r2_path: Source object key (path) in the bucket.
        """
        self.bucket.download_file(Filename=local_path, Key=r2_path)

    def download_memory(self, r2_path: str) -> bytes:
        """Download a single object to memory.

        Params:
            r2_path: Source object key (path) in the bucket.
        """
        return self.bucket.Object(r2_path).get()["Body"].read()

    def download_dir(self, local_path: str, r2_path_dir: str) -> None:
        """Download all objects under a prefix into a local directory.

        Preserves the relative structure under the given prefix.

        Params:
            local_path: Local directory to populate with downloaded files.
            r2_path_dir: Remote prefix to download (treated like a directory).
        """
        for obj in self.bucket.objects.filter(Prefix=r2_path_dir):
            # get the name of the file
            relative_path = os.path.relpath(obj.key, r2_path_dir)

            # get the local_path/name_of_the_file
            local_file_path = os.path.join(local_path, relative_path)

            # creates the folder local_path if needed
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            self.bucket.download_file(obj.key, local_file_path)

    def download_stream(self, r2_path: str, chunk_size: int = 8192) -> Iterator[bytes]:
        """Yield the object bytes in chunks (streaming download).

        Params:
            r2_path: Source object key (path) in the bucket.
            chunk_size: Number of bytes per yielded chunk.

        Yields:
            Raw bytes chunks until EOF.
        """
        obj = self.bucket.Object(r2_path)
        try:
            response = obj.get()
            body = response["Body"]

            try:
                yield from iter(lambda: body.read(chunk_size), b"")
            finally:
                body.close()

        except botocore.exceptions.ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchKey"):
                raise FileNotFoundError(
                    f"Object '{r2_path}' not found in bucket '{self.r2_bucket_name}'"
                ) from e
            raise

    def rm(self, r2_path: str) -> None:
        """Delete a single object by key.

        Params:
            r2_path: Object key (path) to delete.
        """
        self.bucket.Object(r2_path).delete()

    def rmdir(self, r2_path: str) -> None:
        """Delete all objects under a given prefix (acts like `rm -r`).

        Params:
            r2_path: Prefix to match and delete (e.g., "folder/").
        """
        for obj in self.bucket.objects.filter(Prefix=r2_path):
            obj.delete()
