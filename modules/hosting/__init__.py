"""BrainrotHustler file hosting.

- **upload** → your own Cloudflare R2 bucket (S3-compatible). Works from
  datacenter IPs and allows commercial use. Configure via the environment /
  OpenClaw store (see ``TOOLS.md``). Uploads are pruned afterwards — see ``r2.prune``.
- **download** → save any http(s) URL to a local file.
"""

from . import r2  # noqa: F401  (boto3 is imported lazily)
from .download import DEFAULT_MAX_BYTES, DownloadError, download, filename_from
from .r2 import (
    R2Error,
    is_configured,
    keep_count,
    list_objects,
    object_key,
    public_url,
    prune,
    quota_bytes,
    upload,
    upload_bytes,
    upload_file,
    usage,
)

__all__ = [
    "r2", "R2Error", "upload", "upload_file", "upload_bytes", "object_key",
    "public_url", "is_configured", "list_objects", "prune", "usage",
    "keep_count", "quota_bytes",
    "download", "filename_from", "DownloadError", "DEFAULT_MAX_BYTES",
]
