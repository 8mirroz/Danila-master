"""Prove the staging S3 backend stores and restores tenant-safe artifacts.

The verifier creates one isolated object through the application storage API,
checks its canonical URI, object metadata and round-trip SHA-256, then deletes
both the remote object and its materialized cache before exiting.
"""

from __future__ import annotations

import hashlib
import io
import sys
import uuid
from pathlib import Path

from botocore.exceptions import ClientError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.automation.storage import S3FileStorage
from settings import settings


def _require_s3() -> None:
    settings.validate_auth_configuration()
    if settings.STORAGE_BACKEND != "s3":
        raise RuntimeError("This verifier must run with PARTSOPS_STORAGE_BACKEND=s3")
    if not settings.S3_ENDPOINT_URL:
        raise RuntimeError("This verifier requires a configured S3 endpoint")


def main() -> None:
    _require_s3()
    suffix = uuid.uuid4().hex[:12]
    tenant_id = f"s3-proof-{suffix}"
    artifact_id = f"art-s3-{suffix}"
    filename = "rfq.csv"
    payload = b"part_number,quantity\nPROOF-001,2\n"
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    storage = S3FileStorage()
    stored_path: str | None = None

    try:
        stored_path, safe_filename, size = storage.save_file(
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            file_obj=io.BytesIO(payload),
            original_filename=filename,
        )
        expected_key = "/".join(
            part
            for part in (settings.S3_PREFIX, tenant_id, safe_filename)
            if part
        )
        expected_uri = f"s3://{settings.S3_BUCKET}/{expected_key}"
        if stored_path != expected_uri or size != len(payload):
            raise RuntimeError("S3 canonical URI or object size did not match")

        head = storage._client().head_object(Bucket=settings.S3_BUCKET, Key=expected_key)
        if head.get("Metadata") != {"tenant-id": tenant_id, "artifact-id": artifact_id}:
            raise RuntimeError("S3 object metadata did not retain tenant ownership")
        if storage.calculate_sha256(stored_path) != expected_sha256:
            raise RuntimeError("S3 materialized content hash did not match")

        storage.delete_file(stored_path)
        stored_path = None
        try:
            storage._client().head_object(Bucket=settings.S3_BUCKET, Key=expected_key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
                raise
        else:
            raise RuntimeError("S3 verifier cleanup did not remove the temporary object")

        print("staging_s3_storage=passed upload=1 restore=1 cleanup=1")
    finally:
        if stored_path is not None:
            storage.delete_file(stored_path)


if __name__ == "__main__":
    main()
