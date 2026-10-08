"""Backward-compatibility CLI runner for python -m youtube_playlist_downloader."""
import warnings
from main import main

warnings.warn(
    "'python -m youtube_playlist_downloader' is deprecated in v2.0.0. "
    "Please run 'python main.py' or 'python run_youtube_downloader.py' directly.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    main()
