#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Workflow logic for IDM and Normal modes"""

from typing import List, Optional, Tuple
import os
import subprocess

from utils import now, sanitize_filename, looks_like_cookie_issue, speak, get_random_delay, sleep_with_cancel, CANCEL_EVENT, human_bytes
from extractor import extract_direct_download_info
from downloaders import add_to_idm, download_and_merge_with_progress, download_file_with_progress
from files_io import remove_url_from_file


def process_single_video_idm(video_url: str, idx: int, total: int, format_choice: str,
                             quality_choice: Optional[str], cookies_file: str,
                             playlist_folder: str, urls_file: str, progress_callback=None, log_callback=None) -> bool:
    log = log_callback if log_callback else print
    log(f"\n[{now()}] 📹 Processing video {idx}/{total}: {video_url}")
    info, error = extract_direct_download_info(video_url, format_choice, quality_choice, cookies_file)
    if error:
        log(f"[{now()}] ❌ Error: {error}")
        if looks_like_cookie_issue(error):
            log(f"[{now()}] ⚠️ Cookie invalid. Update cookie file and retry.")
            speak("Your cookie seems invalid. Please update it.")
            return False
        return False

    safe_title = sanitize_filename(info["title"]) if info else "video"
    filename = f"{safe_title}.{info['ext']}"

    # Extract metadata for GUI
    if format_choice == "1":
        quality_info = f" [{info.get('bitrate', 'unknown')}]"
        quality_display = info.get('bitrate', 'unknown')
        format_display = "Audio Only"
    elif format_choice in ("2", "3"):
        quality_info = f" [{info.get('resolution', 'unknown')}]"
        quality_display = info.get('resolution', 'unknown')
        format_display = "Video Only" if format_choice == "2" else "Video+Audio"
    else:
        quality_info = ""
        quality_display = "unknown"
        format_display = "unknown"

    # Get file size estimate
    from downloaders import _head_content_length
    from utils import human_bytes

    if info.get("needs_merge", False):
        total_guess = (_head_content_length(info.get("video_url")) or 0) + (_head_content_length(info.get("audio_url")) or 0)
        file_size_display = human_bytes(total_guess) if total_guess > 0 else "Unknown"
    else:
        size_guess = _head_content_length(info.get("direct_url"))
        file_size_display = human_bytes(size_guess) if size_guess else "Unknown"

    # Define file_id for both GUI and CLI
    file_id = f"video_{idx}"

    # Notify GUI with metadata
    if progress_callback:
        progress_callback(
            file_id=file_id,
            current_file=safe_title,
            file_size=file_size_display,
            quality=quality_display,
            format_type=format_display,
            percent=0
        )

    if info.get("needs_merge", False):
        log(f"[{now()}] 🔀 Video+Audio separate: downloading with IDM, then merging{quality_info}")

        # Generate temp filenames
        import tempfile
        import time as _t
        temp_suffix = int(_t.time() * 1000)
        v_tmp = os.path.join(playlist_folder, f"temp_video_{safe_title}_{temp_suffix}.{info.get('video_ext', 'mp4')}")
        a_tmp = os.path.join(playlist_folder, f"temp_audio_{safe_title}_{temp_suffix}.{info.get('audio_ext', 'm4a')}")

        # Download video with IDM
        log(f"[{now()}] ⬇️ Downloading video stream with IDM...")
        if not add_to_idm(info["video_url"], playlist_folder, os.path.basename(v_tmp), log_callback):
            log(f"[{now()}] ❌ IDM video download failed. Falling back to Python mode.")
            # Fallback to Python download
            output_path = os.path.join(playlist_folder, filename)
            header_desc = f"(IDM→Python) Processing {idx}/{total}: {video_url} | {safe_title}{quality_info}"
            ok = download_and_merge_with_progress(
                info["video_url"], info["audio_url"], output_path,
                info.get("video_ext", "mp4"), info.get("audio_ext", "m4a"),
                header_desc=header_desc, position=0,
                progress_callback=progress_callback, file_id=file_id,
                use_chunks=True,  # Enable chunks
                log_callback=log_callback
            )
            if ok:
                remove_url_from_file(urls_file, video_url)
                if progress_callback:
                    progress_callback(file_id=file_id, completed=True)
            else:
                if progress_callback:
                    progress_callback(file_id=file_id, completed=True)
            return ok

        # Small delay between IDM calls
        sleep_with_cancel(2)

        # Download audio with IDM
        log(f"[{now()}] ⬇️ Downloading audio stream with IDM...")
        if not add_to_idm(info["audio_url"], playlist_folder, os.path.basename(a_tmp), log_callback):
            log(f"[{now()}] ❌ IDM audio download failed.")
            # Clean up video if it exists
            try:
                if os.path.exists(v_tmp):
                    log(f"[{now()}] 🧹 Cleaning up partial video file...")
                    os.remove(v_tmp)
            except Exception as e:
                log(f"[{now()}] ⚠️ Could not clean temp video: {e}")
            if progress_callback:
                progress_callback(file_id=file_id, completed=True)
            return False

        # Wait for IDM to finish downloads (poll for file completion)
        log(f"[{now()}] ⏳ Waiting for IDM to complete downloads...")
        log(f"[{now()}] 💡 Monitor IDM window for download progress")
        import time
        max_wait = 3600  # 60 minutes max
        wait_start = time.time()

        while time.time() - wait_start < max_wait:
            if CANCEL_EVENT.is_set():
                log(f"[{now()}] ⛔ Canceled while waiting for IDM")
                try:
                    if os.path.exists(v_tmp): os.remove(v_tmp)
                    if os.path.exists(a_tmp): os.remove(a_tmp)
                except: pass
                if progress_callback:
                    progress_callback(file_id=file_id, completed=True)
                return False

            if os.path.exists(v_tmp) and os.path.exists(a_tmp):
                # Check if files are still being written (size changes)
                try:
                    v_size_1 = os.path.getsize(v_tmp)
                    a_size_1 = os.path.getsize(a_tmp)
                    time.sleep(3)  # Wait 3 seconds
                    v_size_2 = os.path.getsize(v_tmp)
                    a_size_2 = os.path.getsize(a_tmp)

                    # If sizes haven't changed, downloads are complete
                    if v_size_1 == v_size_2 and a_size_1 == a_size_2 and v_size_1 > 0 and a_size_1 > 0:
                        log(f"[{now()}] ✅ IDM downloads complete: Video {human_bytes(v_size_1)}, Audio {human_bytes(a_size_1)}")
                        break
                except Exception as e:
                    log(f"[{now()}] ⚠️ Error checking file sizes: {e}")

            time.sleep(5)  # Check every 5 seconds

        if not (os.path.exists(v_tmp) and os.path.exists(a_tmp)):
            log(f"[{now()}] ❌ IDM downloads incomplete after waiting. Files missing.")
            try:
                if os.path.exists(v_tmp): os.remove(v_tmp)
                if os.path.exists(a_tmp): os.remove(a_tmp)
            except: pass
            if progress_callback:
                progress_callback(file_id=file_id, completed=True)
            return False

        # Merge with FFmpeg
        log(f"[{now()}] 🔧 Merging video and audio streams with FFmpeg...")
        output_path = os.path.join(playlist_folder, filename)
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", v_tmp, "-i", a_tmp,
            "-c:v", "copy", "-c:a", "copy",
            output_path
        ]
        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)

        # Clean up temp files
        try:
            if os.path.exists(v_tmp):
                os.remove(v_tmp)
                log(f"[{now()}] 🧹 Cleaned temp video file")
            if os.path.exists(a_tmp):
                os.remove(a_tmp)
                log(f"[{now()}] 🧹 Cleaned temp audio file")
        except Exception as e:
            log(f"[{now()}] ⚠️ Could not clean temp files: {e}")

        if result.returncode == 0:
            log(f"[{now()}] ✅ Merged and saved with IDM: {filename}")
            remove_url_from_file(urls_file, video_url)
            if progress_callback:
                progress_callback(file_id=file_id, percent=100, completed=True)
            return True
        else:
            log(f"[{now()}] ❌ FFmpeg merge failed: {result.stderr}")
            if progress_callback:
                progress_callback(file_id=file_id, completed=True)
            return False
    else:
        log(f"[{now()}] ➕ Adding to IDM: {filename}{quality_info}")
        if add_to_idm(info["direct_url"], playlist_folder, filename, log_callback):
            log(f"[{now()}] ✅ Added to IDM.")
            remove_url_from_file(urls_file, video_url)
            if progress_callback:
                progress_callback(file_id=file_id, percent=100, completed=True)
            return True
        else:
            log(f"[{now()}] ❌ IDM add failed. Consider Normal mode.")
            if progress_callback:
                progress_callback(file_id=file_id, completed=True)
            return False


def process_single_video_normal(video_url: str, idx: int, total: int, format_choice: str,
                                quality_choice: Optional[str], cookies_file: str,
                                playlist_folder: str, urls_file: str,
                                position: int = 0, progress_callback=None, log_callback=None) -> Tuple[str, bool]:
    log = log_callback if log_callback else print
    if CANCEL_EVENT.is_set():
        return video_url, False
    try:
        info, error = extract_direct_download_info(video_url, format_choice, quality_choice, cookies_file)
        if error:
            log(f"[{now()}] ❌ Error: {error}")
            return video_url, False
        safe_title = sanitize_filename(info["title"]) if info else "video"
        filename = f"{safe_title}.{info['ext']}"
        output_path = os.path.join(playlist_folder, filename)

        # Extract metadata
        if format_choice == "1":
            quality_info = f" [{info.get('bitrate', 'unknown')}]"
            quality_display = info.get('bitrate', 'unknown')
            format_display = "Audio Only"
        elif format_choice in ("2", "3"):
            quality_info = f" [{info.get('resolution', 'unknown')}]"
            quality_display = info.get('resolution', 'unknown')
            format_display = "Video Only" if format_choice == "2" else "Video+Audio"
        else:
            quality_info = ""
            quality_display = "unknown"
            format_display = "unknown"

        header_desc = f"(Normal) Processing {idx}/{total}: {video_url} | {safe_title}{quality_info}"
        from downloaders import _head_content_length
        from utils import human_bytes
        total_guess = (_head_content_length(info.get("video_url")) or 0 + _head_content_length(info.get("audio_url")) or 0) if info.get("needs_merge", False) else _head_content_length(info.get("direct_url"))
        file_size_display = human_bytes(total_guess) if (total_guess and total_guess > 0) else "Unknown"

        log(f"\n[{now()}] 📹 {header_desc} => [0B/{file_size_display} at: 0.00 Mbps]")

        # Notify GUI with metadata
        if progress_callback:
            file_id = f"video_{idx}"
            progress_callback(
                file_id=file_id,
                current_file=safe_title,
                file_size=file_size_display,
                quality=quality_display,
                format_type=format_display,
                percent=0
            )
        # Normal sequential download (STABLE)
        # Chunks disabled - causing issues

        log(f"[{now()}] 🔄 Starting download: {safe_title}")

        if info.get("needs_merge", False):
            ok = download_and_merge_with_progress(
                info["video_url"], info["audio_url"], output_path,
                info.get("video_ext", "mp4"), info.get("audio_ext", "m4a"),
                header_desc=header_desc, position=position,
                progress_callback=progress_callback, file_id=file_id,
                use_chunks=True,  # ENABLED - multi-connection parallel download
                log_callback=log_callback
            )
        else:
            ok = download_file_with_progress(info["direct_url"], output_path, header_desc=header_desc, position=position,
                                            progress_callback=progress_callback, file_id=file_id,
                                            use_chunks=True,  # ENABLED - multi-connection parallel download
                                            log_callback=log_callback
                                            )
        if ok:
            remove_url_from_file(urls_file, video_url)
            if progress_callback:
                progress_callback(file_id=f"video_{idx}", percent=100, completed=True)
        else:
            if progress_callback:
                progress_callback(file_id=f"video_{idx}", completed=True)
        return video_url, ok
    except Exception as e:
        log(f"[{now()}] ❌ Unexpected failure: {e}")
        return video_url, False


def process_batch_idm_with_monitoring(video_urls: List[str], format_choice: str, quality_choice: Optional[str],
                                      cookies_file: str, playlist_folder: str, urls_file: str,
                                      wait_time: int, short_delay: int, use_random: bool,
                                      batch_size: int = 5,
                                      progress_callback=None, log_callback=None) -> List[str]:
    log = log_callback if log_callback else print
    failed_videos: List[str] = []
    batch_count = 0
    for idx, video_url in enumerate(video_urls, start=1):
        if CANCEL_EVENT.is_set():
            break
        # Update progress callback
        if progress_callback:
            progress_callback(current=idx-1, total=len(video_urls), current_file=f"Processing {idx}/{len(video_urls)}")

        success = process_single_video_idm(
            video_url, idx, len(video_urls), format_choice, quality_choice, cookies_file, playlist_folder, urls_file, progress_callback, log_callback
        )
        if not success:
            failed_videos.append(video_url)
        else:
            # Update after success
            if progress_callback:
                progress_callback(current=idx, total=len(video_urls), percent=100)
        # short delay between adds
        if use_random:
            import random
            delay = random.uniform(short_delay * 0.8, short_delay * 1.2)
            sleep_with_cancel(delay)
        else:
            sleep_with_cancel(short_delay)
        # wait after every batch_size videos
        if idx % batch_size == 0 and idx < len(video_urls):
            batch_count += 1
            if batch_count % 3 == 0:
                log(f"\n[{now()}] 🔍 Checking cookie health…")
                # Best-effort; skip actual call to keep decoupled
            if use_random:
                actual_wait = get_random_delay(wait_time // 60)
                log(f"\n[{now()}] ⏸️ Waiting ~{actual_wait//60} minutes before next batch…")
            else:
                actual_wait = wait_time
                log(f"\n[{now()}] ⏸️ Waiting {wait_time//60} minutes before next batch…")
            sleep_with_cancel(actual_wait)
    return failed_videos


def process_batches_normal(video_urls: List[str], format_choice: str, quality_choice: Optional[str],
                           cookies_file: str, playlist_folder: str, urls_file: str,
                           wait_time: int, use_random: bool,
                           batch_size: int = 5,
                           progress_callback=None, log_callback=None) -> List[str]:
    log = log_callback if log_callback else print
    failed_videos: List[str] = []
    total = len(video_urls)
    batch_count = 0
    completed = 0

    for batch_start in range(0, total, batch_size):
        if CANCEL_EVENT.is_set():
            break
        batch = video_urls[batch_start:batch_start + batch_size]
        log(f"\n[{now()}] ▶️ Starting batch {batch_start//batch_size + 1} with {len(batch)} item(s) - downloading sequentially with full chunks…")

        # Process videos SEQUENTIALLY with FULL CHUNKS
        # Cards will be created by process_single_video_normal when download starts
        for i, url in enumerate(batch):
            if CANCEL_EVENT.is_set():
                break

            # Download single video - it will update the card with real info
            video_url, ok = process_single_video_normal(
                url,
                batch_start + i + 1,
                total,
                format_choice,
                quality_choice,
                cookies_file,
                playlist_folder,
                urls_file,
                0,  # position=0 since sequential
                progress_callback,
                log_callback
            )

            if ok:
                completed += 1
                if progress_callback:
                    progress_callback(current=completed, total=total, percent=100)
            else:
                failed_videos.append(video_url)

        # batch finished
        batch_count += 1
        if batch_start + len(batch) < total:
            if use_random:
                from utils import get_random_delay
                actual_wait = get_random_delay(wait_time // 60)
                log(f"\n[{now()}] ⏸️ Waiting ~{actual_wait//60} minutes before next batch…")
            else:
                actual_wait = wait_time
                log(f"\n[{now()}] ⏸️ Waiting {wait_time//60} minutes before next batch…")
            sleep_with_cancel(actual_wait)
    return failed_videos
