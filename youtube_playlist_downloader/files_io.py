"""Compatibility wrapper for files_io module in youtube_playlist_downloader."""
import warnings
import importlib

warnings.warn(
    "Importing from 'youtube_playlist_downloader.files_io' is deprecated in v2.0.0; "
    "use 'import files_io' directly.",
    DeprecationWarning,
    stacklevel=2,
)

_mod = importlib.import_module("files_io")

for _k, _v in _mod.__dict__.items():
    if not _k.startswith("__") or _k in ("__doc__", "__all__"):
        globals()[_k] = _v
