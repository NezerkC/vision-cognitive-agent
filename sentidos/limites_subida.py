"""Upload size limits for the local gateway.

Upload endpoints used to read the whole request body into memory, so a single large upload could exhaust RAM.
read_upload_limited() reads in chunks and stops with 413 as soon as the configured limit is exceeded.
"""

import os

from fastapi import HTTPException, UploadFile

DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024


def max_upload_bytes() -> int:
    """Upload limit in bytes, from VISION_MAX_UPLOAD_BYTES (default 50 MB)."""
    raw = os.environ.get("VISION_MAX_UPLOAD_BYTES")
    if raw is None:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        value = int(raw)
    except ValueError as e:
        raise ValueError(f"VISION_MAX_UPLOAD_BYTES must be a positive integer, got {raw!r}") from e
    if value <= 0:
        raise ValueError(f"VISION_MAX_UPLOAD_BYTES must be a positive integer, got {raw!r}")
    return value


async def read_upload_limited(file: UploadFile, max_bytes: int | None = None) -> bytes:
    """Read an upload fully, raising HTTP 413 once it exceeds max_bytes."""
    limit = max_upload_bytes() if max_bytes is None else max_bytes
    data = bytearray()
    while chunk := await file.read(_CHUNK_SIZE):
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(status_code=413, detail=f"File exceeds the {limit} byte upload limit.")
    return bytes(data)
