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
    """
    Implements pure Python requests logic with chunking and FFmpeg merging.
    """
    
    def _download_chunk(self, url: str, start: int, end: int, chunk_id: int, 
                        temp_folder: str, progress_dict: dict, cancel_event: threading.Event,
                        headers: Optional[dict] = None) -> tuple:
        try:
            req_headers = headers.copy() if headers else {}
            req_headers['Range'] = f'bytes={start}-{end}'
            response = requests.get(url, headers=req_headers, timeout=(10, 60), stream=True)
            response.raise_for_status()

            chunk_path = os.path.join(temp_folder, f"chunk_{chunk_id}.part")
            chunk_downloaded = 0
            with open(chunk_path, 'wb') as f:
                for data in response.iter_content(chunk_size=1024 * 256):
                    if cancel_event.is_set():
                        return chunk_id, False, chunk_path, chunk_downloaded
                    f.write(data)
                    chunk_downloaded += len(data)
                    progress_dict[chunk_id] = chunk_downloaded
            return chunk_id, True, chunk_path, chunk_downloaded
        except Exception:
            return chunk_id, False, None, 0

    def _download_single_stream(self, url: str, target_path: str, use_chunks: bool,
                                header_desc: str, task_id: str, 
                                progress_callback: Callable[[str, float, str], None],
                                cancel_event: threading.Event, total_override: Optional[int] = None,
                                initial_downloaded: int = 0, overall_total: Optional[int] = None,
                                headers: Optional[dict] = None) -> bool:
        """Downloads a single URL (either chunked or sequential)."""
        total = total_override or _head_content_length(url, headers=headers)
        # Use provided overall_total for percent calculation if present, otherwise total
        calc_total = overall_total if overall_total else total

        supports_ranges = False
        if use_chunks and total and total > 2 * 1024 * 1024:
            try:
                r = requests.head(url, headers=headers, allow_redirects=True, timeout=(5, 10))
                if r.headers.get('Accept-Ranges', '') == 'bytes' or 'googlevideo.com' in url:
                    supports_ranges = True
            except Exception:
                pass

        start_time = _t.time()

        if supports_ranges and use_chunks:
            temp_dir = tempfile.mkdtemp(prefix=f"dl_chunks_{uuid.uuid4().hex[:8]}_")
            
            num_chunks = 6
            if total > 100 * 1024 * 1024: num_chunks = 16
            elif total > 50 * 1024 * 1024: num_chunks = 12
            elif total > 20 * 1024 * 1024: num_chunks = 10
            elif total > 10 * 1024 * 1024: num_chunks = 8

            chunk_size = total // num_chunks
            chunk_progress = {}
            chunk_tasks = []
            
            for i in range(num_chunks):
                start_byte = i * chunk_size
                end_byte = start_byte + chunk_size - 1 if i < num_chunks - 1 else total - 1
                chunk_progress[i] = 0
                chunk_tasks.append((url, start_byte, end_byte, i, temp_dir, chunk_progress, cancel_event, headers))

            chunk_results = {}
            progress_running = True
            
            def update_progress_thread():
                last_downloaded = 0
                while progress_running:
                    try:
                        current_downloaded = sum(chunk_progress.values())
                        if current_downloaded != last_downloaded:
                            elapsed = max(_t.time() - start_time, 1e-6)
                            # total_downloaded includes previously downloaded streams (like video before audio)
                            total_downloaded = initial_downloaded + current_downloaded
                            mbps = (total_downloaded * 8.0) / 1_000_000.0 / elapsed
                            
                            active_chunks = sum(1 for v in chunk_progress.values() if v > 0)
                            
                            percent = (total_downloaded / calc_total) * 100 if calc_total else 0
                            status_msg = f"{human_bytes(total_downloaded)}/{human_bytes(calc_total)} at {mbps:.2f} Mbps [Chunks: {active_chunks}]"
                            progress_callback(task_id, percent, status_msg)
                            
                            last_downloaded = current_downloaded
                    except Exception:
                        pass
                    _t.sleep(0.3)

            pt = threading.Thread(target=update_progress_thread, daemon=True)
            pt.start()

            fallback = False
            with ThreadPoolExecutor(max_workers=num_chunks) as executor:
                futures = {executor.submit(self._download_chunk, *task): task[3] for task in chunk_tasks}
                for future in as_completed(futures):
                    if cancel_event.is_set():
                        fallback = True
                        break
                    chunk_id, success, chunk_path, _ = future.result()
                    if success:
                        chunk_results[chunk_id] = chunk_path
                    else:
                        fallback = True
                        break

            progress_running = False
            _t.sleep(0.4)

            if not fallback and not cancel_event.is_set() and len(chunk_results) == num_chunks:
                try:
                    with open(target_path, 'wb') as outfile:
                        for i in sorted(chunk_results.keys()):
                            with open(chunk_results[i], 'rb') as chunk_file:
                                outfile.write(chunk_file.read())
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return True
                except Exception:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    fallback = True
            else:
                shutil.rmtree(temp_dir, ignore_errors=True)
                if cancel_event.is_set():
                    return False
                # fallback to normal
        
        # Normal sequential fallback
        try:
            with requests.get(url, headers=headers, stream=True, timeout=(10, 120)) as r:
                r.raise_for_status()
                if not total:
                    cl = r.headers.get('Content-Length') or r.headers.get('content-length')
                    if cl and cl.isdigit():
                        total = int(cl)
                        calc_total = overall_total if overall_total else total
                
                downloaded = 0
                with open(target_path, 'wb', buffering=8*1024*1024) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if cancel_event.is_set():
                            f.close()
                            if os.path.exists(target_path): os.remove(target_path)
                            return False
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            elapsed = max(_t.time() - start_time, 1e-6)
                            total_downloaded = initial_downloaded + downloaded
                            mbps = (total_downloaded * 8.0) / 1_000_000.0 / elapsed
                            percent = (total_downloaded / calc_total) * 100 if calc_total else 0
                            status_msg = f"{human_bytes(total_downloaded)}/{human_bytes(calc_total)} at {mbps:.2f} Mbps"
                            progress_callback(task_id, percent, status_msg)
            return True
        except Exception as e:
            print(f"OUTER DOWN ERR: {e}")
            if os.path.exists(target_path):
                try: os.remove(target_path)
                except: pass
            return False

    def download(self, info: dict, config: DownloadConfig, task_id: str,
                 progress_callback: Callable[[str, float, str], None],
                 cancel_event: threading.Event) -> bool:
        
        output_path = resolve_output_path(config.output_dir, info.get("title", "video"), info.get("ext", "mp4"))
        
        if info.get("needs_merge", False):
            # Two streams
            temp_dir = tempfile.gettempdir()
            uid = uuid.uuid4().hex[:8]
            v_tmp = os.path.join(temp_dir, f"tmp_v_{uid}.{info.get('video_ext', 'mp4')}")
            a_tmp = os.path.join(temp_dir, f"tmp_a_{uid}.{info.get('audio_ext', 'm4a')}")
            
            headers = info.get("http_headers", {})
            v_size = _head_content_length(info["video_url"], headers=headers) or 0
            a_size = _head_content_length(info["audio_url"], headers=headers) or 0
            total_size = v_size + a_size if (v_size + a_size) > 0 else None

            try:
                # Video
                progress_callback(task_id, 0, "Starting video download...")
                print(f"DEBUG HEADERS: {headers}")
                v_ok = self._download_single_stream(
                    info["video_url"], v_tmp, True, "Video stream", task_id, progress_callback,
                    cancel_event, total_override=v_size, overall_total=total_size, headers=headers
                )
                if not v_ok or cancel_event.is_set():
                    return False
                
                # Audio
                progress_callback(task_id, (v_size/total_size*100) if total_size else 50, "Starting audio download...")
                print(f"DEBUG HEADERS: {headers}")
                a_ok = self._download_single_stream(
                    info["audio_url"], a_tmp, True, "Audio stream", task_id, progress_callback,
                    cancel_event, total_override=a_size, initial_downloaded=v_size, overall_total=total_size, headers=headers
                )
                if not a_ok or cancel_event.is_set():
                    return False
                
                progress_callback(task_id, 99, "Merging with FFmpeg...")
                
                # Merge
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-i", v_tmp, "-i", a_tmp,
                    "-c:v", "copy", "-c:a", "copy",
                    output_path
                ]
                proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                while proc.poll() is None:
                    if cancel_event.is_set():
                        proc.terminate()
                        return False
                    _t.sleep(0.1)
                return proc.returncode == 0
                
            finally:
                if os.path.exists(v_tmp):
                    try: os.remove(v_tmp)
                    except: pass
                if os.path.exists(a_tmp):
                    try: os.remove(a_tmp)
                    except: pass
        else:
            # Single stream
            headers = info.get("http_headers", {})
            progress_callback(task_id, 0, "Starting download...")
            print(f"DEBUG HEADERS: {headers}")
            return self._download_single_stream(
                info["direct_url"], output_path, True, "Stream", task_id, progress_callback,
                cancel_event, headers=headers
            )


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
