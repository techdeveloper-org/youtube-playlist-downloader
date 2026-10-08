"""Compatibility wrapper for formats module in youtube_playlist_downloader."""
import warnings
import importlib

warnings.warn(
    "Importing from 'youtube_playlist_downloader.formats' is deprecated in v2.0.0; "
    "use 'import formats' directly.",
    DeprecationWarning,
    stacklevel=2,
)

_mod = importlib.import_module("formats")

for _k, _v in _mod.__dict__.items():
    if not _k.startswith("__") or _k in ("__doc__", "__all__"):
        globals()[_k] = _v
