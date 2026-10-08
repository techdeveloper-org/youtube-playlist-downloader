"""Backward-compatibility package shim for youtube_playlist_downloader.

DEPRECATION NOTICE:
Direct usage of the 'youtube_playlist_downloader' package namespace is deprecated in v2.0.0
and will be removed in v3.0.0. All modules have moved to the root repository.
"""

import warnings
import importlib

warnings.warn(
    "The 'youtube_playlist_downloader' package namespace is deprecated in v2.0.0 and will be removed in v3.0.0. "
    "Please import modules directly from the root namespace (e.g., 'import utils', 'import main').",
    DeprecationWarning,
    stacklevel=2,
)

_AVAILABLE_SUBMODULES = {
    "choices", "deps", "downloaders", "extractor", "files_io",
    "formats", "gui", "main", "paths", "speedtest_utils", "utils", "workflow",
}


def __getattr__(name: str):
    """Provide lazy attribute resolution for submodules in conformance with PEP 562.

    Parameters:
        name: Name of the submodule to resolve dynamically.

    Returns:
        The imported module object.

    Raises:
        AttributeError: If name is not a known submodule.
    """
    if name in _AVAILABLE_SUBMODULES:
        return importlib.import_module(f"youtube_playlist_downloader.{name}")
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
