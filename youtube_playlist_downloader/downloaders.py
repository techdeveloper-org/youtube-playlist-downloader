#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Downloaders: IDM integration and Python progress download/merge"""

import os
import subprocess
from typing import Optional

from .deps import requests, tqdm
from .utils import now, human_bytes, CANCEL_EVENT
from .paths import find_idm


def add_to_idm(direct_url: str, out_folder: str, filename: str, log_callback=None) -> bool:
    log = log_callback if log_callback else print
    idm_path = find_idm()
    if not idm_path or not os.path.exists(idm_path):
        log(f"[{now()}] ⚠️ IDM not found. Falling back to Normal mode for this item.")
        return False

    log(f"[{now()}] 🚀 Starting IDM: {filename}")
    log(f"[{now()}] 📍 IDM Path: {idm_path}")

    # Start download immediately without /n flag to allow IDM to use optimal settings
    # Removed /n (silent mode) as it may prevent IDM from using max connection count
    # The /s flag will be used after adding to ensure queue starts immediately
    cmd = [idm_path, "/d", direct_url, "/p", out_folder, "/f", filename]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log(f"[{now()}] ✅ IDM download started (PID: {process.pid})")

        # Start the download queue immediately to ensure full-speed processing
        import time
        time.sleep(0.5)  # Brief delay to ensure download is registered in queue
        start_cmd = [idm_path, "/s"]
        try:
            subprocess.Popen(start_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            log(f"[{now()}] 🚀 IDM queue started - processing at full speed")
        except Exception:
            pass  # Queue start is optional, download will still proceed

        log(f"[{now()}] 💡 IDM downloading in background. Monitor IDM window for progress.")
        log(f"[{now()}] ℹ️ If speed is still slow, check IDM settings:")
        log(f"[{now()}]    • Options → Connection → 'Default max. conn. number' = 16-32")
        log(f"[{now()}]    • Downloads → Speed Limiter → Turn off")
        return True
    except Exception as e:
        log(f"[{now()}] ❌ Failed to start IDM: {e}")
        return False


def _head_content_length(url: str, timeout: int = 30) -> Optional[int]:
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        if r.status_code >= 400:
            return None
        cl = r.headers.get('Content-Length') or r.headers.get('content-length')
        return int(cl) if cl and cl.isdigit() else None
    except Exception:
        return None


def download_chunk(url: str, start: int, end: int, chunk_id: int, temp_folder: str,
                   progress_dict: dict = None) -> tuple:
    """Download a single chunk of file (byte range request)"""
    try:
        headers = {'Range': f'bytes={start}-{end}'}
        # timeout = (connect_timeout, read_timeout)
        # This prevents hanging if connection stalls during read
        response = requests.get(url, headers=headers, timeout=(10, 60), stream=True)
        response.raise_for_status()

        chunk_path = os.path.join(temp_folder, f"chunk_{chunk_id}.part")
        chunk_downloaded = 0
        with open(chunk_path, 'wb') as f:
            for data in response.iter_content(chunk_size=1024 * 256):
                if CANCEL_EVENT.is_set():
                    return chunk_id, False, chunk_path, chunk_downloaded
                f.write(data)
                chunk_downloaded += len(data)
                # Update shared progress dict if provided (dict update is atomic in Python)
                if progress_dict is not None:
                    progress_dict[chunk_id] = chunk_downloaded
        return chunk_id, True, chunk_path, chunk_downloaded
    except Exception as e:
        # Return failure but don't print error (too noisy for parallel chunks)
        return chunk_id, False, None, 0


def download_file_with_progress(url: str, output_path: str, header_desc: str, position: int = 0,
                                progress_callback=None, file_id: str = None, use_chunks: bool = True,
                                log_callback=None) -> bool:
    total = _head_content_length(url)
    bar = None
    downloaded = 0
    import time as _t
    start_time = _t.time()

    log = log_callback if log_callback else print

    # Debug logging
    log(f"[{now()}] 🔍 File size: {human_bytes(total) if total else 'Unknown'}, Chunks: {use_chunks}")

    # Check if server supports range requests
    supports_ranges = False
    if use_chunks and total and total > 2 * 1024 * 1024:  # Only for files > 2MB
        try:
            r = requests.head(url, allow_redirects=True, timeout=(5, 10))  # Fast check
            accepts = r.headers.get('Accept-Ranges', '')
            supports_ranges = accepts == 'bytes'
            log(f"[{now()}] 🔍 Accept-Ranges: {accepts}, Supports: {supports_ranges}")
        except Exception as e:
            log(f"[{now()}] ⚠️ HEAD request failed: {e}")
            supports_ranges = False

    # For YouTube, assume range support (they always support it)
    if use_chunks and total and 'googlevideo.com' in url:
        supports_ranges = True
        log(f"[{now()}] ✅ YouTube URL detected - enabling chunks")

    # Use chunked parallel download if supported
    if supports_ranges and use_chunks:
        log(f"[{now()}] 🚀 Starting chunked download...")
        import tempfile
        temp_dir = tempfile.mkdtemp(prefix="dl_chunks_")

        # Determine optimal number of chunks based on file size
        # Sequential downloads allow full chunk power without connection exhaustion
        if total > 100 * 1024 * 1024:  # > 100MB
            num_chunks = 16  # More chunks for large files
        elif total > 50 * 1024 * 1024:  # > 50MB
            num_chunks = 12
        elif total > 20 * 1024 * 1024:  # > 20MB
            num_chunks = 10
        elif total > 10 * 1024 * 1024:  # > 10MB
            num_chunks = 8
        else:
            num_chunks = 6  # Smaller files

        chunk_size = total // num_chunks
        log(f"[{now()}] 📦 Using {num_chunks} chunks of {human_bytes(chunk_size)} each")

        try:
            if tqdm:
                total_str = human_bytes(total)
                init_desc = f"{header_desc} => [0B/{total_str} at: 0.00 Mbps]"
                bar = tqdm(total=total, unit='B', unit_scale=True, desc=init_desc, position=position, leave=True, dynamic_ncols=True)

            # Create chunk download tasks with shared progress tracking
            from concurrent.futures import ThreadPoolExecutor, as_completed
            import threading
            chunk_progress = {}  # Shared dict for tracking chunk progress
            chunk_progress_lock = threading.Lock()

            chunk_tasks = []
            for i in range(num_chunks):
                start_byte = i * chunk_size
                end_byte = start_byte + chunk_size - 1 if i < num_chunks - 1 else total - 1
                chunk_progress[i] = 0
                chunk_tasks.append((url, start_byte, end_byte, i, temp_dir, chunk_progress))

            # Download chunks in parallel with progress tracking thread
            chunk_results = {}
            progress_running = True

            def update_progress_thread():
                """Background thread to update progress from chunk downloads"""
                last_downloaded = 0
                while progress_running:
                    try:
                        current_downloaded = sum(chunk_progress.values())  # Dict read is thread-safe

                        if current_downloaded != last_downloaded and bar:
                            bar.update(current_downloaded - last_downloaded)
                            elapsed = max(_t.time() - start_time, 1e-6)
                            mbps = (current_downloaded * 8.0) / 1_000_000.0 / elapsed

                            # Count active chunks (downloading) and completed chunks
                            active_chunks = sum(1 for v in chunk_progress.values() if v > 0)
                            completed_chunks = len(chunk_results)

                            cur_desc = f"{header_desc} => [{human_bytes(current_downloaded)}/{human_bytes(total)} at: {mbps:.2f} Mbps] [Active: {active_chunks}/{num_chunks} | Done: {completed_chunks}/{num_chunks}]"
                            bar.set_description(cur_desc)
                            if progress_callback and file_id:
                                percent = (current_downloaded / total) * 100 if total else 0
                                status = f"{human_bytes(current_downloaded)}/{human_bytes(total)} at {mbps:.2f} Mbps [Active: {active_chunks}/{num_chunks}]"
                                progress_callback(file_id=file_id, percent=percent, status=status)
                            last_downloaded = current_downloaded
                    except Exception:
                        pass  # Ignore errors in progress thread
                    _t.sleep(0.3)  # Update every 0.3 seconds for smoother progress

            progress_thread = threading.Thread(target=update_progress_thread, daemon=True)
            progress_thread.start()

            with ThreadPoolExecutor(max_workers=num_chunks) as executor:
                futures = {executor.submit(download_chunk, *task): task[3] for task in chunk_tasks}

                # Process chunk results as they complete
                for future in as_completed(futures):
                    if CANCEL_EVENT.is_set():
                        progress_running = False
                        break

                    try:
                        chunk_id, success, chunk_path, chunk_bytes = future.result()
                        if success:
                            chunk_results[chunk_id] = chunk_path
                        else:
                            # One chunk failed - stop all and fallback
                            log(f"[{now()}] ⚠️ Chunk {chunk_id} failed, falling back to normal")
                            progress_running = False
                            if bar:
                                bar.close()
                            import shutil
                            shutil.rmtree(temp_dir, ignore_errors=True)
                            use_chunks = False
                            break
                    except Exception as e:
                        # Error in chunk - fallback to normal
                        log(f"[{now()}] ⚠️ Chunk error: {e}, falling back to normal")
                        progress_running = False
                        if bar:
                            bar.close()
                        import shutil
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        use_chunks = False
                        break

            progress_running = False  # Stop progress thread
            _t.sleep(0.5)  # Give progress thread time to finish

            # Only proceed if all chunks downloaded successfully
            if use_chunks and len(chunk_results) == num_chunks and not CANCEL_EVENT.is_set():
                # Combine chunks in order
                log(f"[{now()}] 🔧 Combining {num_chunks} chunks...")
                try:
                    with open(output_path, 'wb') as outfile:
                        for i in sorted(chunk_results.keys()):
                            chunk_path = chunk_results[i]
                            with open(chunk_path, 'rb') as chunk_file:
                                outfile.write(chunk_file.read())

                    if bar:
                        bar.close()

                    # Clean up temp directory
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    log(f"[{now()}] ✅ Chunked download successful!")
                    return True
                except Exception as e:
                    # Error combining chunks - fallback
                    if bar:
                        bar.close()
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    log(f"[{now()}] ❌ Chunk combination failed: {e}, falling back to normal download")
                    use_chunks = False
            elif CANCEL_EVENT.is_set():
                if bar:
                    bar.close()
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                try:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                except:
                    pass
                log(f"[{now()}] ⛔ Canceled: {header_desc}")
                return False
            else:
                # Not all chunks completed - already fell back to normal
                pass

        except Exception as e:
            if bar:
                bar.close()
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            log(f"[{now()}] ❌ Chunked download failed, falling back to normal: {e}")
            # Fallback to normal download
            use_chunks = False

    # Normal sequential download (fallback or when chunks not supported)
    if not use_chunks or not supports_ranges:
        log(f"[{now()}] 📥 Using normal sequential download")
    try:
        if tqdm:
            total_str = human_bytes(total)
            init_desc = f"{header_desc} => [0B/{total_str} at: 0.00 Mbps]"
            bar = tqdm(total=total if (total and total > 0) else None, unit='B', unit_scale=True, desc=init_desc, position=position, leave=True, dynamic_ncols=True)
        with requests.get(url, stream=True, timeout=(10, 120)) as r:  # 10s connect, 120s read
            r.raise_for_status()
            if (not total) and bar is not None:
                cl = r.headers.get('Content-Length') or r.headers.get('content-length')
                if cl and cl.isdigit():
                    total = int(cl)
                    bar.total = total
                    bar.refresh()
            # Larger buffer for faster writes (8 MB)
            with open(output_path, 'wb', buffering=8*1024*1024) as f:
                # Larger chunk size for faster downloads (1 MB)
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if CANCEL_EVENT.is_set():
                        try:
                            f.close()
                        except Exception:
                            pass
                        try:
                            if os.path.exists(output_path):
                                os.remove(output_path)
                        except Exception:
                            pass
                        if bar is not None:
                            bar.close()
                        log(f"[{now()}] ⛔ Canceled: {header_desc}")
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if bar is not None:
                            bar.update(len(chunk))
                            elapsed = max(_t.time() - start_time, 1e-6)
                            mbps = (downloaded * 8.0) / 1_000_000.0 / elapsed
                            cur_desc = f"{header_desc} => [{human_bytes(downloaded)}/{human_bytes(total)} at: {mbps:.2f} Mbps]"
                            bar.set_description(cur_desc)

                            # Send progress to GUI
                            if progress_callback and file_id and total:
                                percent = (downloaded / total) * 100
                                status = f"{human_bytes(downloaded)}/{human_bytes(total)} at {mbps:.2f} Mbps"
                                progress_callback(file_id=file_id, percent=percent, status=status)
        if bar is not None:
            bar.close()
        return True
    except Exception as e:
        if bar is not None:
            bar.close()
        log(f"[{now()}] ❌ Download failed for {header_desc}: {e}")
        return False


def download_and_merge_with_progress(video_url: str, audio_url: str, output_path: str,
                                     video_ext: str = "mp4", audio_ext: str = "m4a",
                                     header_desc: str = "", position: int = 0,
                                     progress_callback=None, file_id: str = None, use_chunks: bool = True,
                                     log_callback=None) -> bool:
    import tempfile
    import time as _t
    temp_dir = tempfile.gettempdir()
    v_tmp = os.path.join(temp_dir, f"temp_video_{int(_t.time()*1000)}.{video_ext}")
    a_tmp = os.path.join(temp_dir, f"temp_audio_{int(_t.time()*1000)}.{audio_ext}")

    log = log_callback if log_callback else print

    v_size = _head_content_length(video_url)
    a_size = _head_content_length(audio_url)
    total = (v_size or 0) + (a_size or 0)
    total = total if total > 0 else None

    # Check if both URLs support range requests for chunked download
    supports_ranges_v = False
    supports_ranges_a = False
    if use_chunks and v_size and v_size > 5 * 1024 * 1024:
        try:
            r = requests.head(video_url, allow_redirects=True, timeout=30)
            supports_ranges_v = r.headers.get('Accept-Ranges') == 'bytes'
        except:
            pass
    if use_chunks and a_size and a_size > 1 * 1024 * 1024:  # Audio usually smaller
        try:
            r = requests.head(audio_url, allow_redirects=True, timeout=30)
            supports_ranges_a = r.headers.get('Accept-Ranges') == 'bytes'
        except:
            pass

    bar = None
    downloaded = 0
    start_time = _t.time()

    # Use chunked download if supported
    if supports_ranges_v and use_chunks:
        try:
            if tqdm:
                total_str = human_bytes(total)
                init_desc = f"{header_desc} => [0B/{total_str} at: 0.00 Mbps]"
                bar = tqdm(total=total, unit='B', unit_scale=True, desc=init_desc, position=position, leave=True, dynamic_ncols=True)

            # Download video with chunks (sequential = full power)
            if v_size > 100 * 1024 * 1024:
                num_chunks_v = 12  # Large videos
            elif v_size > 50 * 1024 * 1024:
                num_chunks_v = 10
            else:
                num_chunks_v = 8
            chunk_size_v = v_size // num_chunks_v
            import tempfile as tf
            temp_chunk_dir = tf.mkdtemp(prefix="dl_chunks_v_")

            from concurrent.futures import ThreadPoolExecutor, as_completed
            chunk_tasks_v = []
            for i in range(num_chunks_v):
                start_byte = i * chunk_size_v
                end_byte = start_byte + chunk_size_v - 1 if i < num_chunks_v - 1 else v_size - 1
                chunk_tasks_v.append((video_url, start_byte, end_byte, i, temp_chunk_dir))

            chunk_results_v = {}
            chunk_progress_v = {}
            with ThreadPoolExecutor(max_workers=num_chunks_v) as executor:
                futures_v = {executor.submit(download_chunk, *task, chunk_progress_v): task[3] for task in chunk_tasks_v}
                for future in as_completed(futures_v):
                    if CANCEL_EVENT.is_set():
                        break
                    chunk_id, success, chunk_path, chunk_bytes = future.result()
                    if success:
                        chunk_results_v[chunk_id] = chunk_path
                        if bar:
                            chunk_downloaded = sum(os.path.getsize(chunk_results_v[i]) for i in sorted(chunk_results_v.keys()))
                            downloaded = chunk_downloaded
                            bar.update(len(chunk_results_v) - bar.n if len(chunk_results_v) > bar.n else 0)
                            elapsed = max(_t.time() - start_time, 1e-6)
                            mbps = (downloaded * 8.0) / 1_000_000.0 / elapsed
                            cur_desc = f"{header_desc} => [{human_bytes(downloaded)}/{human_bytes(total)} at: {mbps:.2f} Mbps]"
                            bar.set_description(cur_desc)
                            if progress_callback and file_id:
                                percent = (downloaded / total) * 100 if total else 0
                                status = f"{human_bytes(downloaded)}/{human_bytes(total)} at {mbps:.2f} Mbps"
                                progress_callback(file_id=file_id, percent=percent, status=status)
                    else:
                        import shutil
                        shutil.rmtree(temp_chunk_dir, ignore_errors=True)
                        if bar:
                            bar.close()
                        # Fallback to normal download
                        use_chunks = False
                        break

            if not CANCEL_EVENT.is_set() and use_chunks and len(chunk_results_v) == num_chunks_v:
                # Combine video chunks
                with open(v_tmp, 'wb') as outfile:
                    for i in sorted(chunk_results_v.keys()):
                        with open(chunk_results_v[i], 'rb') as chunk_file:
                            outfile.write(chunk_file.read())

                import shutil
                shutil.rmtree(temp_chunk_dir, ignore_errors=True)

                # Download audio (normal or chunked based on support)
                if supports_ranges_a and a_size > 1 * 1024 * 1024:
                    # Chunked audio download (fewer chunks since audio is smaller)
                    if a_size > 20 * 1024 * 1024:
                        num_chunks_a = 6
                    else:
                        num_chunks_a = 4
                    chunk_size_a = a_size // num_chunks_a
                    temp_chunk_dir_a = tf.mkdtemp(prefix="dl_chunks_a_")

                    chunk_tasks_a = []
                    for i in range(num_chunks_a):
                        start_byte = i * chunk_size_a
                        end_byte = start_byte + chunk_size_a - 1 if i < num_chunks_a - 1 else a_size - 1
                        chunk_tasks_a.append((audio_url, start_byte, end_byte, i, temp_chunk_dir_a))

                    chunk_results_a = {}
                    chunk_progress_a = {}
                    with ThreadPoolExecutor(max_workers=num_chunks_a) as executor:
                        futures_a = {executor.submit(download_chunk, *task, chunk_progress_a): task[3] for task in chunk_tasks_a}
                        for future in as_completed(futures_a):
                            if CANCEL_EVENT.is_set():
                                break
                            chunk_id, success, chunk_path, chunk_bytes = future.result()
                            if success:
                                chunk_results_a[chunk_id] = chunk_path
                                if bar:
                                    audio_downloaded = sum(os.path.getsize(chunk_results_a[i]) for i in sorted(chunk_results_a.keys()))
                                    downloaded = v_size + audio_downloaded
                                    bar.update(v_size + len(chunk_results_a) * chunk_size_a - bar.n if v_size + len(chunk_results_a) * chunk_size_a > bar.n else 0)
                                    elapsed = max(_t.time() - start_time, 1e-6)
                                    mbps = (downloaded * 8.0) / 1_000_000.0 / elapsed
                                    cur_desc = f"{header_desc} => [{human_bytes(downloaded)}/{human_bytes(total)} at: {mbps:.2f} Mbps]"
                                    bar.set_description(cur_desc)
                                    if progress_callback and file_id:
                                        percent = (downloaded / total) * 100 if total else 0
                                        status = f"{human_bytes(downloaded)}/{human_bytes(total)} at {mbps:.2f} Mbps"
                                        progress_callback(file_id=file_id, percent=percent, status=status)

                    if len(chunk_results_a) == num_chunks_a:
                        # Combine audio chunks
                        with open(a_tmp, 'wb') as outfile:
                            for i in sorted(chunk_results_a.keys()):
                                with open(chunk_results_a[i], 'rb') as chunk_file:
                                    outfile.write(chunk_file.read())
                        shutil.rmtree(temp_chunk_dir_a, ignore_errors=True)
                    else:
                        shutil.rmtree(temp_chunk_dir_a, ignore_errors=True)
                        # Fallback for audio
                        use_chunks = False
                else:
                    # Normal audio download
                    with requests.get(audio_url, stream=True, timeout=60) as r:
                        r.raise_for_status()
                        with open(a_tmp, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=1024 * 256):
                                if CANCEL_EVENT.is_set():
                                    break
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if bar:
                                        bar.update(len(chunk))
                                        elapsed = max(_t.time() - start_time, 1e-6)
                                        mbps = (downloaded * 8.0) / 1_000_000.0 / elapsed
                                        cur_desc = f"{header_desc} => [{human_bytes(downloaded)}/{human_bytes(total)} at: {mbps:.2f} Mbps]"
                                        bar.set_description(cur_desc)
                                        if progress_callback and file_id:
                                            percent = (downloaded / total) * 100 if total else 0
                                            status = f"{human_bytes(downloaded)}/{human_bytes(total)} at {mbps:.2f} Mbps"
                                            progress_callback(file_id=file_id, percent=percent, status=status)

                if bar:
                    bar.close()

                # Check for cancellation before merge
                if CANCEL_EVENT.is_set():
                    try:
                        if os.path.exists(v_tmp): os.remove(v_tmp)
                        if os.path.exists(a_tmp): os.remove(a_tmp)
                    except Exception:
                        pass
                    log(f"[{now()}] ⛔ Canceled before merge: {header_desc}")
                    return False

                # Merge
                ffmpeg_cmd = [
                    "ffmpeg", "-y", "-i", v_tmp, "-i", a_tmp,
                    "-c:v", "copy", "-c:a", "copy",
                    output_path
                ]
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                try:
                    if os.path.exists(v_tmp): os.remove(v_tmp)
                    if os.path.exists(a_tmp): os.remove(a_tmp)
                except Exception:
                    pass
                return result.returncode == 0

        except Exception as e:
            if bar:
                bar.close()
            log(f"[{now()}] ❌ Chunked download/merge failed, falling back to normal: {e}")
            use_chunks = False

    # Normal sequential download (fallback)
    try:
        if tqdm:
            total_str = human_bytes(total)
            init_desc = f"{header_desc} => [0B/{total_str} at: 0.00 Mbps]"
            bar = tqdm(total=total, unit='B', unit_scale=True, desc=init_desc, position=position, leave=True, dynamic_ncols=True)
        # Video
        with requests.get(video_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            # Larger buffer for faster writes
            with open(v_tmp, 'wb', buffering=8*1024*1024) as f:
                # Larger chunk size for faster downloads (1 MB)
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if CANCEL_EVENT.is_set():
                        try:
                            f.close()
                        except Exception:
                            pass
                        try:
                            if os.path.exists(v_tmp): os.remove(v_tmp)
                            if os.path.exists(a_tmp): os.remove(a_tmp)
                        except Exception:
                            pass
                        if bar is not None:
                            bar.close()
                        log(f"[{now()}] ⛔ Canceled: {header_desc}")
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if bar is not None:
                            bar.update(len(chunk))
                            elapsed = max(_t.time() - start_time, 1e-6)
                            mbps = (downloaded * 8.0) / 1_000_000.0 / elapsed
                            cur_desc = f"{header_desc} => [{human_bytes(downloaded)}/{human_bytes(total)} at: {mbps:.2f} Mbps]"
                            bar.set_description(cur_desc)

                            # Send progress to GUI
                            if progress_callback and file_id and total:
                                percent = (downloaded / total) * 100
                                status = f"{human_bytes(downloaded)}/{human_bytes(total)} at {mbps:.2f} Mbps"
                                progress_callback(file_id=file_id, percent=percent, status=status)
        # Audio
        with requests.get(audio_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            # Larger buffer for faster writes
            with open(a_tmp, 'wb', buffering=8*1024*1024) as f:
                # Larger chunk size for faster downloads (1 MB)
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if CANCEL_EVENT.is_set():
                        try:
                            f.close()
                        except Exception:
                            pass
                        try:
                            if os.path.exists(v_tmp): os.remove(v_tmp)
                            if os.path.exists(a_tmp): os.remove(a_tmp)
                        except Exception:
                            pass
                        if bar is not None:
                            bar.close()
                        log(f"[{now()}] ⛔ Canceled: {header_desc}")
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if bar is not None:
                            bar.update(len(chunk))
                            elapsed = max(_t.time() - start_time, 1e-6)
                            mbps = (downloaded * 8.0) / 1_000_000.0 / elapsed
                            cur_desc = f"{header_desc} => [{human_bytes(downloaded)}/{human_bytes(total)} at: {mbps:.2f} Mbps]"
                            bar.set_description(cur_desc)

                            # Send progress to GUI
                            if progress_callback and file_id and total:
                                percent = (downloaded / total) * 100
                                status = f"{human_bytes(downloaded)}/{human_bytes(total)} at {mbps:.2f} Mbps"
                                progress_callback(file_id=file_id, percent=percent, status=status)
        if bar is not None:
            bar.close()

        # Check for cancellation before merge
        if CANCEL_EVENT.is_set():
            try:
                if os.path.exists(v_tmp): os.remove(v_tmp)
                if os.path.exists(a_tmp): os.remove(a_tmp)
            except Exception:
                pass
            log(f"[{now()}] ⛔ Canceled before merge: {header_desc}")
            return False

        # Merge (lossless - no re-encoding)
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", v_tmp, "-i", a_tmp,
            "-c:v", "copy", "-c:a", "copy",
            output_path
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
        try:
            if os.path.exists(v_tmp): os.remove(v_tmp)
            if os.path.exists(a_tmp): os.remove(a_tmp)
        except Exception:
            pass
        return result.returncode == 0
    except Exception as e:
        if bar is not None:
            bar.close()
        log(f"[{now()}] ❌ Download/merge failed: {e}")
        try:
            if os.path.exists(v_tmp): os.remove(v_tmp)
            if os.path.exists(a_tmp): os.remove(a_tmp)
        except Exception:
            pass
        return False
