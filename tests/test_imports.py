"""Unit tests for validating root and shim imports with warning isolation."""
import sys
import unittest
import warnings
import importlib

ROOT_MODULES = [
    "choices", "deps", "downloaders", "extractor", "files_io",
    "formats", "gui", "main", "paths", "speedtest_utils", "utils", 
]

class TestImports(unittest.TestCase):
    """Test module identity and backwards compatibility warnings."""

    def setUp(self):
        """Clear caches to isolate warnings."""
        for mod in ROOT_MODULES:
            sys.modules.pop(mod, None)
            sys.modules.pop(f"youtube_playlist_downloader.{mod}", None)
        sys.modules.pop("youtube_playlist_downloader", None)

    def test_shim_warnings_and_identity(self):
        """Verify shim emits DeprecationWarning and proxies to root module accurately."""
        for mod in ROOT_MODULES:
            with self.subTest(module=mod):
                with warnings.catch_warnings(record=True) as w:
                    warnings.simplefilter("always", DeprecationWarning)
                    root_mod = importlib.import_module(mod)
                    shim_mod = importlib.import_module(f"youtube_playlist_downloader.{mod}")
                    
                    self.assertTrue(any(issubclass(warn.category, DeprecationWarning) for warn in w))
                    
                    # Ensure public functions are identically bound
                    for attr in dir(root_mod):
                        if not attr.startswith("_"):
                            self.assertIs(getattr(shim_mod, attr), getattr(root_mod, attr))
                            
    def test_package_namespace_warning(self):
        """Verify root package import emits warning."""
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            import youtube_playlist_downloader
            self.assertTrue(any(issubclass(warn.category, DeprecationWarning) for warn in w))
