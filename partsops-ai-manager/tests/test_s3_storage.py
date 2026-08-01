from __future__ import annotations

import io
from pathlib import Path

from app.automation.storage import S3FileStorage


class FakeS3:
    def __init__(self):
        self.objects: dict[tuple[str, str], bytes] = {}

    def upload_file(self, filename, bucket, key, ExtraArgs):
        self.objects[(bucket, key)] = Path(filename).read_bytes()

    def download_file(self, bucket, key, filename):
        Path(filename).write_bytes(self.objects[(bucket, key)])

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


def test_s3_storage_keeps_canonical_uri_and_materializes_parser_cache(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    monkeypatch.setenv("PARTSOPS_S3_BUCKET", "beta-bucket")
    monkeypatch.setenv("PARTSOPS_S3_PREFIX", "partsops")
    storage = S3FileStorage()
    fake = FakeS3()
    storage._client_instance = fake

    uri, safe_name, size = storage.save_file(
        "tenant_a", "art_1", io.BytesIO(b"part,qty\nA-1,2\n"), "rfq.csv"
    )

    assert (uri, safe_name, size) == (
        "s3://beta-bucket/partsops/tenant_a/art_1.csv",
        "art_1.csv",
        15,
    )
    cached = storage.materialize(uri)
    assert Path(cached).read_bytes() == b"part,qty\nA-1,2\n"
    assert len(storage.calculate_sha256(uri)) == 64
    storage.delete_file(uri)
    assert fake.objects == {}
