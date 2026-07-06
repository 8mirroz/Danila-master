import io
import os
import pytest
from app.automation.storage import LocalFileStorage

@pytest.fixture
def storage():
    return LocalFileStorage()

def test_exe_rejected(storage):
    f = io.BytesIO(b"MZ\x90\x00\x03\x00")
    f.name = "evil.exe"
    with pytest.raises(ValueError, match="UPLOAD_EXTENSION_NOT_ALLOWED"):
        storage.save_file("tenant_test", "art_exe", f, "evil.exe")

def test_sh_rejected(storage):
    f = io.BytesIO(b"#!/bin/bash\nls")
    f.name = "script.sh"
    with pytest.raises(ValueError, match="UPLOAD_EXTENSION_NOT_ALLOWED"):
        storage.save_file("tenant_test", "art_sh", f, "script.sh")

def test_double_extension_rejected(storage):
    f = io.BytesIO(b"%PDF-1.4")
    f.name = "evil.pdf.exe"
    with pytest.raises(ValueError, match="UPLOAD_EXTENSION_NOT_ALLOWED"):
        storage.save_file("tenant_test", "art_double", f, "evil.pdf.exe")

def test_path_traversal_rejected(storage):
    # Filename with directory traversal characters
    # basename() will strip "../../", so test with a filename that has path separators after basename
    # A more realistic attack: inject a filename with null bytes or absolute path
    f = io.BytesIO(b"%PDF-1.4test")
    # Try injecting null byte which could truncate path in some C-based backends
    f.name = "evil\x00.pdf"
    with pytest.raises(ValueError, match="UPLOAD_INVALID_FILENAME|UPLOAD_EXTENSION_NOT_ALLOWED|UPLOAD_MIME_NOT_ALLOWED"):
        storage.save_file("tenant_test", "art_traversal", f, "evil\x00.pdf")

def test_fake_pdf_rejected(storage):
    f = io.BytesIO(b"NOT_A_PDF_CONTENT")
    f.name = "fake.pdf"
    with pytest.raises(ValueError, match="UPLOAD_MIME_NOT_ALLOWED"):
        storage.save_file("tenant_test", "art_fake_pdf", f, "fake.pdf")

def test_valid_png_accepted(storage):
    png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
    f = io.BytesIO(png_header + b"\x00" * 100)
    f.name = "test.png"
    path, safe_name, size = storage.save_file("tenant_test", "art_png", f, "test.png")
    assert safe_name == "art_png.png"
    assert size > 0
    assert os.path.exists(path)
    os.unlink(path)

def test_oversized_rejected(storage):
    # Create file larger than limit (set limit to 1 byte via monkeypatching settings)
    large_content = b"x" * (16 * 1024 * 1024 + 1)
    f = io.BytesIO(large_content)
    f.name = "big.png"
    # Write a valid PNG header
    f.seek(0)
    f.write(b"\x89PNG\r\n\x1a\n")
    f.seek(0)
    with pytest.raises(ValueError, match="UPLOAD_FILE_TOO_LARGE"):
        storage.save_file("tenant_test", "art_big", f, "big.png")

def test_empty_file_rejected(storage):
    f = io.BytesIO(b"")
    f.name = "empty.pdf"
    with pytest.raises(ValueError, match="UPLOAD_INVALID_CONTENT"):
        storage.save_file("tenant_test", "art_empty", f, "empty.pdf")

def test_valid_csv_accepted(storage):
    csv_content = "name,price,qty\nBrake Pad,4500,1\nOil Filter,800,2\n".encode()
    f = io.BytesIO(csv_content)
    f.name = "catalog.csv"
    path, safe_name, size = storage.save_file("tenant_test", "art_csv", f, "catalog.csv")
    assert safe_name == "art_csv.csv"
    assert size == len(csv_content)
    assert os.path.exists(path)
    os.unlink(path)
