#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dependencies and auto-installer for youtube_playlist_downloader"""

import sys
import subprocess
import importlib


def ensure_package(pkg: str, import_name: str | None = None):
    try:
        return importlib.import_module(import_name or pkg)
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])
        return importlib.import_module(import_name or pkg)


# Core deps
yt_dlp = ensure_package("yt-dlp", "yt_dlp")
requests = ensure_package("requests")

# Optional tqdm
try:
    tqdm = ensure_package("tqdm").tqdm
except Exception:
    tqdm = None

# Optional Ookla Speedtest
try:
    speedtest = ensure_package("speedtest-cli", "speedtest")
except Exception:
    speedtest = None

# Optional CustomTkinter for GUI
try:
    customtkinter = ensure_package("customtkinter")
except Exception:
    customtkinter = None
