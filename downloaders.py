#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Downloaders: Strategy Pattern for downloading videos."""

import os
import subprocess
import threading
import time as _t
import tempfile
import shutil
import uuid
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from deps import requests
from utils import now, human_bytes
from paths import find_idm
from model import DownloadConfig

from abc import ABC, abstractmethod


class DownloaderStrategy(ABC):
    @abstractmethod
    def download(self, info: dict, config: DownloadConfig, task_id: str,
                 progress_callback: Callable[[str, float, str], None],
                 cancel_event: threading.Event) -> bool:
        """
        Executes the download process. Must handle partial file cleanup on cancel_event.is_set().
        """
        pass


def _head_content_length(url: str, timeout: int = 30, headers: Optional[dict] = None) -> Optional[int]:
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if r.status_code >= 400:
            return None
        cl = r.headers.get('Content-Length') or r.headers.get('content-length')
        return int(cl) if cl and cl.isdigit() else None
    except Exception:
        return None


def resolve_output_path(output_dir: str, title: str, ext: str) -> str:
    """Resolves output path, avoiding conflicts."""
    import re
    # Basic sanitize
    safe_title = "".join(c for c in title if c.isalnum() or c in " -_().[]").rstrip()
    if not safe_title:
        safe_title = "video"
    
    base_path = os.path.join(output_dir, f"{safe_title}.{ext}")
    if not os.path.exists(base_path):
        return base_path
    
    # Conflict resolution
    i = 1
    while True:
        new_path = os.path.join(output_dir, f"{safe_title}_{i}.{ext}")
        if not os.path.exists(new_path):
            return new_path
        i += 1


class PythonDownloader(DownloaderStrategy):
    def download(self, info: dict, config: DownloadConfig, task_id: str,
                 progress_callback: Callable[[str, float, str], None],
                 cancel_event: threading.Event) -> bool:
        
        output_path = resolve_output_path(config.output_dir, info.get("title", "video"), info.get("ext", "mp4"))
        
        def yt_dlp_hook(d):
            if cancel_event.is_set():
                raise Exception("Cancelled by user")
            if d['status'] == 'downloading':
                pct_str = d.get('_percent_str', '0.0%').replace('%', '').strip()
                try:
                    import re
                    pct_str = re.sub(r'\x1b\[[0-9;]*m', '', pct_str)
                    percent = float(pct_str)
                except:
                    percent = 0.0
                
                speed = d.get('_speed_str', '').strip()
                try:
                    speed = re.sub(r'\x1b\[[0-9;]*m', '', speed)
                except:
                    pass
                eta = d.get('_eta_str', '').strip()
                try:
                    eta = re.sub(r'\x1b\[[0-9;]*m', '', eta)
                except:
                    pass
                progress_callback(task_id, percent, f"{percent:.1f}% at {speed} ETA {eta}")
            elif d['status'] == 'finished':
                progress_callback(task_id, 99.0, "Merging/Finalizing...")
                
        import yt_dlp
        ydl_opts = {
            'format': info.get('raw_format_id', 'best'),
            'outtmpl': output_path,
            'progress_hooks': [yt_dlp_hook],
            'quiet': True,
            'noprogress': True
        }
        if config.cookies_file:
            ydl_opts['cookiefile'] = config.cookies_file
            
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([info.get('original_url', info.get('video_url', ''))])
            return True
        except Exception as e:
            if "Cancelled by user" in str(e):
                return False
            print(f"PYTHON DOWN ERROR: {e}")
            return False

class IDMDownloader(DownloaderStrategy):
    def __init__(self, fallback_strategy: DownloaderStrategy = None):
        self.fallback = fallback_strategy or PythonDownloader()
        
    def _add_to_idm(self, url: str, out_folder: str, filename: str) -> bool:
        idm_path = find_idm()
        if not idm_path or not os.path.exists(idm_path):
            return False
            
        cmd = [idm_path, "/d", url, "/p", out_folder, "/f", filename, "/n", "/a"]
        try:
            subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _t.sleep(0.5)
            try:
                subprocess.Popen([idm_path, "/s"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"MAIN DOWN ERROR: {e}")
            return False

    def download(self, info: dict, config: DownloadConfig, task_id: str,
                 progress_callback: Callable[[str, float, str], None],
                 cancel_event: threading.Event) -> bool:
                 
        output_path = resolve_output_path(config.output_dir, info.get("title", "video"), info.get("ext", "mp4"))
        filename = os.path.basename(output_path)
        
        if info.get("needs_merge", False):
            progress_callback(task_id, 50, "Dispatching to IDM (Video+Audio)...")
            
            uid = uuid.uuid4().hex[:8]
            v_name = f"tmp_v_{uid}.{info.get('video_ext', 'mp4')}"
            a_name = f"tmp_a_{uid}.{info.get('audio_ext', 'm4a')}"
            v_tmp = os.path.join(config.output_dir, v_name)
            a_tmp = os.path.join(config.output_dir, a_name)
            
            if not self._add_to_idm(info["video_url"], config.output_dir, v_name):
                return self.fallback.download(info, config, task_id, progress_callback, cancel_event)
                
            _t.sleep(2) # delay between adds
            
            if not self._add_to_idm(info["audio_url"], config.output_dir, a_name):
                # Cleanup video if possible, but IDM might hold it
                return False
                
            # Wait for IDM
            progress_callback(task_id, 80, "Waiting for IDM to finish...")
            wait_start = _t.time()
            max_wait = 3600
            
            while _t.time() - wait_start < max_wait:
                if cancel_event.is_set():
                    return False
                if os.path.exists(v_tmp) and os.path.exists(a_tmp):
                    try:
                        v1, a1 = os.path.getsize(v_tmp), os.path.getsize(a_tmp)
                        _t.sleep(3)
                        v2, a2 = os.path.getsize(v_tmp), os.path.getsize(a_tmp)
                        if v1 == v2 and a1 == a2 and v1 > 0 and a1 > 0:
                            break
                    except Exception:
                        pass
                _t.sleep(5)
                
            if not (os.path.exists(v_tmp) and os.path.exists(a_tmp)):
                return False
                
            progress_callback(task_id, 99, "Merging with FFmpeg...")
            ffmpeg_cmd = [
                "ffmpeg", "-y", "-i", v_tmp, "-i", a_tmp,
                "-c:v", "copy", "-c:a", "copy",
                output_path
            ]
            try:
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=300)
                success = (result.returncode == 0)
            except Exception:
                success = False
            
            try:
                if os.path.exists(v_tmp): os.remove(v_tmp)
                if os.path.exists(a_tmp): os.remove(a_tmp)
            except Exception:
                pass
                
            return success
        else:
            progress_callback(task_id, 100, "Dispatching to IDM...")
            if self._add_to_idm(info["direct_url"], config.output_dir, filename):
                return True
            else:
                return self.fallback.download(info, config, task_id, progress_callback, cancel_event)
