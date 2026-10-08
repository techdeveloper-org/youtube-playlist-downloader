"""Compatibility wrapper for choices module in youtube_playlist_downloader."""
import warnings
import importlib

warnings.warn(
    "Importing from 'youtube_playlist_downloader.choices' is deprecated in v2.0.0; "
    "use 'import choices' directly.",
    DeprecationWarning,
    stacklevel=2,
)

_mod = importlib.import_module("choices")

for _k, _v in _mod.__dict__.items():
    if not _k.startswith("__") or _k in ("__doc__", "__all__"):
        globals()[_k] = _v
