#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Speed test utilities (Ookla + HTTP fallback) and auto selection mapping"""

from typing import Optional, Tuple

from .deps import speedtest, requests
from .utils import now
from .paths import find_idm


def measure_network_speed_ookla() -> Optional[float]:
    if not speedtest:
        return None
    try:
        print(f"[{now()}] ⏳ Using Ookla Speedtest… please wait (10-20s)")
        st = speedtest.Speedtest(secure=True)
        st.get_servers([])
        st.get_best_server()
        down_bps = st.download(threads=None)
        if hasattr(st, "results") and getattr(st.results, "download", None):
            down_bps = max(down_bps, st.results.download)
        return down_bps / 1_000_000.0
    except Exception as e:
        print(f"[{now()}] ⚠️ Ookla measurement failed: {e}. Falling back.")
        return None


def measure_network_speed(test_size_bytes: int = 8 * 1024 * 1024, per_request_timeout: int = 15) -> Optional[float]:
    test_urls = [
        "https://speed.hetzner.de/100MB.bin",
        "https://download.thinkbroadband.com/100MB.zip",
        "http://ipv4.download.thinkbroadband.com/100MB.zip",
    ]
    best_mbps: float = 0.0
    sess = requests.Session()
    import time as _t
    for url in test_urls:
        try:
            print(f"[{now()}] ⏳ Testing against {url}…")
            start = _t.perf_counter()
            bytes_read = 0
            with sess.get(url, stream=True, timeout=per_request_timeout) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=1024 * 512):
                    if not chunk:
                        continue
                    bytes_read += len(chunk)
                    if bytes_read >= test_size_bytes:
                        break
            elapsed = max(_t.perf_counter() - start, 1e-6)
            mbps = (bytes_read * 8.0) / 1_000_000.0 / elapsed
            best_mbps = max(best_mbps, mbps)
        except Exception as e:
            print(f"[{now()}] ⚠️ Failed {url}: {e}")
            continue
    return best_mbps if best_mbps > 0 else None


def auto_select_settings(mbps: Optional[float]) -> Tuple[int, int, bool, str, Optional[str], str]:
    if mbps is None:
        print(f"[{now()}] ⚠️ Could not measure network speed. Using conservative defaults.")
        idm_present = find_idm() is not None
        method = "1" if idm_present else "2"
        return (8 * 60, 3, True, "3", "2", method)

    print(f"[{now()}] 🌐 Measured network speed: {mbps:.2f} Mbps")

    if mbps > 10:
        wait_time = 5 * 60
        short_delay = 2
        use_random = False
    elif mbps > 1:
        wait_time = 8 * 60
        short_delay = 3
        use_random = True
    else:
        wait_time = 12 * 60
        short_delay = 5
        use_random = True

    format_choice = "3"
    if mbps <= 1:
        quality_choice = "1"
    elif mbps <= 10:
        quality_choice = "2"
    else:
        quality_choice = "3"

    method = "1" if find_idm() else "2"

    return wait_time, short_delay, use_random, format_choice, quality_choice, method
