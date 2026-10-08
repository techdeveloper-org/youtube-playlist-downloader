#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Utility functions and shared state"""

import os
import time
import datetime
import platform
import subprocess
import threading
from typing import Optional

# Global cancel flag
CANCEL_EVENT = threading.Event()


def now() -> str:
    return datetime.datetime.now().strftime("%H:%M:%S")


def sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in " -_().[]").rstrip()


def human_bytes(n: Optional[int]) -> str:
    if n is None:
        return "?"
    try:
        n = float(n)
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        i = 0
        while n >= 1024 and i < len(units) - 1:
            n /= 1024.0
            i += 1
        if i == 0:
            return f"{int(n)}{units[i]}"
        return f"{n:.2f}{units[i]}"
    except Exception:
        return "?"


def speak(text: str):
    try:
        if platform.system() == "Windows":
            subprocess.call(['mshta', f'javascript:var sh=new ActiveXObject("SAPI.SpVoice"); sh.Speak("{text}");close()'])
        elif platform.system() == "Darwin":
            subprocess.call(['say', text])
        elif platform.system() == "Linux":
            subprocess.call(['espeak', text])
    except Exception:
        pass


COOKIE_ERROR_KEYWORDS = [
    "cookie", "cookies", "login", "sign in", "sign-in", "sign in to confirm", "login_required",
    "please sign in", "authentication", "not available in your country", "age-restricted",
    "This video is private", "private video", "sign in to confirm", "login_required"
]


def cookies_file_is_stale(path: str) -> bool:
    try:
        mtime = os.path.getmtime(path)
        age_days = (time.time() - mtime) / (60*60*24)
        return age_days > 14
    except Exception:
        return True


def looks_like_cookie_issue(error_text: str) -> bool:
    if not error_text:
        return False
    text = error_text.lower()
    return any(k in text for k in COOKIE_ERROR_KEYWORDS)


def get_random_delay(base_minutes: int) -> int:
    import random
    min_delay = int(base_minutes * 0.8 * 60)
    max_delay = int(base_minutes * 1.2 * 60)
    return random.randint(min_delay, max_delay)


def sleep_with_cancel(seconds: float):
    end = time.time() + seconds
    while time.time() < end and not CANCEL_EVENT.is_set():
        remaining = end - time.time()
        time.sleep(min(0.2, remaining))
