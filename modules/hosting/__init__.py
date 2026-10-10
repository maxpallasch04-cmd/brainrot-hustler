"""BrainrotHustler file hosting: catbox (permanent) + litterbox (temporary)."""

from .catbox import (
    CATBOX_MAX_BYTES,
    LITTERBOX_MAX_BYTES,
    LITTERBOX_TIMES,
    UploadError,
    upload,
    upload_bytes,
    upload_file,
)
from .download import DEFAULT_MAX_BYTES, DownloadError, download, filename_from

__all__ = [
    "upload", "upload_file", "upload_bytes", "UploadError",
    "download", "filename_from", "DownloadError", "DEFAULT_MAX_BYTES",
    "CATBOX_MAX_BYTES", "LITTERBOX_MAX_BYTES", "LITTERBOX_TIMES",
]
