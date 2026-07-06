import os
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Tuple
from settings import settings

logger = logging.getLogger("storage")

class LocalFileStorage:
    """
    Handles physical file storage for PartsOps with secure ingestion pipeline:
    Receive → Size Guard → Filename Normalize → Extension Check → MIME Sniff → Magic Bytes Check → Hash → Safe Persist → Audit Event
    """
    def __init__(self):
        self.base_dir = Path(settings.UPLOAD_DIR).absolute()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, tenant_id: str, artifact_id: str, file_obj, original_filename: str) -> Tuple[str, str, int]:
        """
        Saves a file-like object to disk with strict validation.
        Returns (stored_path, safe_filename, size_bytes).
        """
        # Validate tenant_id to prevent directory traversal
        clean_tenant = "".join([c for c in tenant_id if c.isalnum() or c in ('-', '_')]).strip()
        if not clean_tenant or clean_tenant != tenant_id:
            raise ValueError("UPLOAD_INVALID_FILENAME")

        # 1. Clean original filename
        base_name = str(original_filename)
        # Reject null bytes and unicode control characters which can cause path truncation
        if '\x00' in base_name or any(ord(c) < 32 for c in base_name):
            raise ValueError("UPLOAD_INVALID_FILENAME")
        base_name = os.path.basename(base_name)
        if not base_name or base_name in ('.', '..'):
            raise ValueError("UPLOAD_INVALID_FILENAME")

        # 2. Extract and check extension
        parts = base_name.split('.')
        if len(parts) < 2:
            raise ValueError("UPLOAD_EXTENSION_NOT_ALLOWED")

        ext = parts[-1].lower().strip()
        if ext not in settings.UPLOAD_ALLOWED_EXTENSIONS:
            raise ValueError("UPLOAD_EXTENSION_NOT_ALLOWED")

        # Double extension check for security
        for part in parts[:-1]:
            if part.lower() in ('exe', 'sh', 'bat', 'cmd', 'py', 'js', 'scr', 'pif', 'msi'):
                raise ValueError("UPLOAD_EXTENSION_NOT_ALLOWED")

        # 3. Read first chunk for magic bytes validation (MIME Sniffing)
        try:
            first_chunk = file_obj.read(4096)
        except Exception as e:
            logger.error("Failed to read upload stream: %r", e)
            raise ValueError("UPLOAD_INVALID_CONTENT")

        if not first_chunk:
            raise ValueError("UPLOAD_INVALID_CONTENT")

        is_valid_magic = False
        if ext == "pdf":
            is_valid_magic = first_chunk.startswith(b"%PDF")
        elif ext == "png":
            is_valid_magic = first_chunk.startswith(b"\x89PNG\r\n\x1a\n")
        elif ext in ("jpg", "jpeg"):
            is_valid_magic = first_chunk.startswith(b"\xff\xd8\xff")
        elif ext == "xlsx":
            is_valid_magic = first_chunk.startswith(b"PK\x03\x04")
        elif ext == "csv":
            try:
                first_chunk.decode('utf-8')
                is_valid_magic = True
            except UnicodeDecodeError:
                try:
                    first_chunk.decode('latin1')
                    is_valid_magic = True
                except Exception:
                    is_valid_magic = False
        else:
            is_valid_magic = False

        if settings.ENABLE_STRICT_UPLOAD_VALIDATION and not is_valid_magic:
            raise ValueError("UPLOAD_MIME_NOT_ALLOWED")

        # 4. Generate safe filename using artifact_id
        safe_filename = f"{artifact_id}.{ext}"

        # Ensure tenant directory exists
        tenant_dir = self.base_dir / clean_tenant
        tenant_dir.mkdir(parents=True, exist_ok=True)

        stored_path = tenant_dir / safe_filename

        # 5. Size check and write loop
        size = len(first_chunk)
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if size > max_bytes:
            raise ValueError("UPLOAD_FILE_TOO_LARGE")

        try:
            with open(stored_path, "wb") as f:
                f.write(first_chunk)
                while chunk := file_obj.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_bytes:
                        f.close()
                        if stored_path.exists():
                            stored_path.unlink()
                        raise ValueError("UPLOAD_FILE_TOO_LARGE")
                    f.write(chunk)
        except ValueError:
            raise
        except Exception as e:
            logger.error("Storage write error: %r", e)
            if stored_path.exists():
                stored_path.unlink()
            raise ValueError("UPLOAD_STORAGE_ERROR")

        # 6. Structured logging
        logger.info(f"UPLOAD_ACCEPTED: tenant={tenant_id}, file={original_filename}, safe_name={safe_filename}, size={size}")

        return str(stored_path), safe_filename, size

    def calculate_sha256(self, file_path: str) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def delete_file(self, stored_path: str):
        path = Path(stored_path)
        if path.exists():
            path.unlink()

# Singleton for app-wide use
storage = LocalFileStorage()
