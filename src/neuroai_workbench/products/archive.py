from __future__ import annotations

import io
import zipfile
from datetime import datetime

CANONICAL_DOCUMENT_TIME = datetime(2000, 1, 1, 0, 0, 0)
CANONICAL_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
CANONICAL_COMPRESSION = zipfile.ZIP_STORED
CANONICAL_EXTERNAL_ATTR = 0o600 << 16


def canonical_zip_info(filename: str) -> zipfile.ZipInfo:
    """Return fixed ZIP member metadata for reproducible OPC packages."""
    info = zipfile.ZipInfo(filename=filename, date_time=CANONICAL_ZIP_DATE)
    info.compress_type = CANONICAL_COMPRESSION
    info.create_system = 3
    info.create_version = 20
    info.extract_version = 20
    info.flag_bits = 0
    info.internal_attr = 0
    info.external_attr = CANONICAL_EXTERNAL_ATTR
    info.extra = b""
    info.comment = b""
    return info


def render_deterministic_zip(entries: list[tuple[str, bytes]], *, sort_entries: bool = True) -> bytes:
    """Render entries with fixed metadata and reject ambiguous duplicate names."""
    filenames = [filename for filename, _ in entries]
    if len(filenames) != len(set(filenames)):
        raise ValueError("deterministic archive entries must have unique filenames")

    ordered_entries = sorted(entries, key=lambda item: item[0]) if sort_entries else entries
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=CANONICAL_COMPRESSION, allowZip64=True) as archive:
        archive.comment = b""
        for filename, payload in ordered_entries:
            archive.writestr(canonical_zip_info(filename), payload, compress_type=CANONICAL_COMPRESSION)
    return buffer.getvalue()


def canonicalize_zip_payload(payload: bytes) -> bytes:
    """Normalize a ZIP/OPC package without changing member payloads."""
    with zipfile.ZipFile(io.BytesIO(payload), "r") as source:
        entries = [(info.filename, source.read(info)) for info in source.infolist()]
    return render_deterministic_zip(entries)
