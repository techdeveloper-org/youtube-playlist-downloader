#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""User choices: auto/manual, format/quality, method, cookies"""

import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from typing import Optional, Tuple

from utils import now, cookies_file_is_stale
from extractor import extract_direct_download_info


def choose_auto_or_manual() -> bool:
    print("\n" + "="*60)
    print("🧠 START MODE:")
    print("="*60)
    print("  1. Auto select (recommended)")
    print("  2. Manual select")
    print("="*60)
    choice = input("Enter your choice [1/2]: ").strip()
    if choice not in ("1", "2"):
        print(f"[{now()}] ❌ Invalid choice, defaulting to Auto.")
        choice = "1"
    return choice == "1"


def get_download_speed_config() -> Tuple[int, int, bool]:
    print("\n" + "="*60)
    print("⚡ CHOOSE DOWNLOAD SPEED:")
    print("="*60)
    print("  1. 🚀 Fast (5 min wait)")
    print("  2. 🐢 Medium (8 min wait) [RECOMMENDED]")
    print("  3. 🛡️ Slow (12 min wait)")
    print("="*60)
    speed_choice = input("Enter your choice [1/2/3]: ").strip()
    if speed_choice == "1":
        wait_time = 5
        delay = 2
    elif speed_choice == "3":
        wait_time = 12
        delay = 5
    else:
        wait_time = 8
        delay = 3
    print(f"[{now()}] ⏳ Applying speed profile, please wait…")
    print(f"[{now()}] ✅ Selected: {'Fast' if speed_choice=='1' else ('Slow' if speed_choice=='3' else 'Medium')}")
    # Ask randomization
    print("\n" + "="*60)
    print("🎲 USE RANDOM DELAYS? (Recommended)")
    print("="*60)
    random_choice = input("Enable random delays? [Y/n]: ").strip().lower()
    use_random = random_choice != 'n'
    return wait_time * 60, delay, use_random


def get_user_choices() -> Tuple[str, Optional[str]]:
    print("\n" + "="*60)
    print("📋 CHOOSE DOWNLOAD FORMAT:")
    print("="*60)
    print("  1. Audio only")
    print("  2. Video only (no audio)")
    print("  3. Video with audio (combined)")
    print("="*60)
    format_choice = input("Enter your choice [1/2/3]: ").strip()
    if format_choice not in ("1", "2", "3"):
        format_choice = "3"
    quality_choice = None
    if format_choice == "1":
        print("\n" + "="*60)
        print("🔊 CHOOSE AUDIO QUALITY:")
        print("="*60)
        print("  1. Low (≤64kbps)")
        print("  2. Medium (96-128kbps)")
        print("  3. Best (highest)")
        quality_choice = input("Enter your choice [1/2/3]: ").strip()
        if quality_choice not in ("1", "2", "3"):
            quality_choice = "3"
    elif format_choice in ("2", "3"):
        print("\n" + "="*60)
        print("🎥 CHOOSE VIDEO QUALITY:")
        print("="*60)
        print("  1. Low (360p or lower)")
        print("  2. Medium (480p-720p)")
        print("  3. Best (highest)")
        quality_choice = input("Enter your choice [1/2/3]: ").strip()
        if quality_choice not in ("1", "2", "3"):
            quality_choice = "3"
    print(f"[{now()}] ⏳ Applying format/quality, please wait…")
    return format_choice, quality_choice


def get_download_method() -> str:
    print("\n" + "="*60)
    print("⬇️ CHOOSE DOWNLOAD METHOD:")
    print("="*60)
    print("  1. IDM (Internet Download Manager)")
    print("  2. Normal (Python)")
    print("="*60)
    method = input("Enter your choice [1/2]: ").strip()
    if method not in ("1", "2"):
        method = "1"
    print(f"[{now()}] ⏳ Applying method, please wait…")
    return method


def check_cookies(cookies_file: str):
    import os
    if not os.path.exists(cookies_file) or cookies_file_is_stale(cookies_file):
        print(f"\n[{now()}] ⚠️ Cookie file missing or stale.")
        print(f"👉 Please export fresh cookies manually and save to:\n   {cookies_file}")
        input("Press Enter after cookie file is ready…")


def check_cookie_health(test_url: str, cookies_file: str) -> bool:
    try:
        info, error = extract_direct_download_info(
            test_url, format_choice="1", quality_choice="1", cookiefile=cookies_file
        )
        return error is None
    except Exception:
        return False


def get_merge_prefs() -> tuple[bool, str]:
    """Ask user if they prefer lossless merge and desired container.
    Returns (prefer_lossless, preferred_container). preferred_container is 'mp4' or 'mkv'.
    """
    print("\n" + "="*60)
    print("🧩 MERGE PREFERENCES:")
    print("="*60)
    print("Prefer lossless merge (no compression) when possible?")
    print("  Y = copy streams into compatible container (no re-encode)")
    print("  N = keep MP4 and transcode audio if needed")
    ans = input("Enable lossless merge? [Y/n]: ").strip().lower()
    prefer_lossless = (ans != 'n')
    preferred_container = 'mp4'
    if prefer_lossless:
        print("\nIf streams are not MP4-compatible (e.g., VP9/AV1 + Opus), choose fallback container:")
        print("  1) MKV (recommended)\n  2) MP4 (may transcode)")
        c = input("Select container [1/2]: ").strip()
        preferred_container = 'mkv' if c == '1' else 'mp4'
    print("[{}] ⏳ Applying merge preferences, please wait…".format(now()))
    return prefer_lossless, preferred_container
