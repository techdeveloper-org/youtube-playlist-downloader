#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Playlist and direct info extraction"""

from typing import Dict, List, Optional, Tuple
import json
import subprocess

from deps import yt_dlp
from formats import select_audio_format, select_video_format, select_combined_format


def is_playlist_url(url: str) -> bool:
    """Check if URL is a playlist or single video"""
    # YouTube playlist URLs contain 'list=' parameter
    return 'list=' in url and 'youtube.com' in url


def _run_with_cancellation(cmd: List[str], cancel_event=None) -> Tuple[int, str, str]:
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    while proc.poll() is None:
        if cancel_event and cancel_event.is_set():
            proc.terminate()
            return -1, "", "Canceled"
        import time; time.sleep(0.1)
    stdout, stderr = proc.communicate()
    return proc.returncode, stdout, stderr

def extract_playlist_info(url: str, cancel_event=None) -> Tuple[str, List[Tuple[str, str]]]:
    """Extract video titles and URLs from either a playlist or single video URL"""
    if is_playlist_url(url):
        code, stdout, stderr = _run_with_cancellation(["yt-dlp", "--flat-playlist", "--dump-single-json", url], cancel_event)
        if code != 0:
            raise RuntimeError(stderr.strip() or "yt-dlp failed to extract playlist info")
        data = json.loads(stdout)
        title = data.get("title", "Playlist")
        
        items = []
        for e in data.get("entries", []):
            v_url = e.get("url") or (f"https://www.youtube.com/watch?v={e['id']}" if 'id' in e else None)
            if v_url:
                video_title = e.get("title", f"Video {e.get('id', 'unknown')}")
                items.append((video_title, v_url))
        return title, items
    else:
        code, stdout, stderr = _run_with_cancellation(["yt-dlp", "--dump-single-json", "--no-playlist", url], cancel_event)
        if code != 0:
            raise RuntimeError(stderr.strip() or "yt-dlp failed to extract video info")
        data = json.loads(stdout)
        title = data.get("title", "Video")
        video_url = data.get("webpage_url") or data.get("url") or url
        return title, [(title, video_url)]


def extract_direct_download_info(video_url: str, format_choice: str, quality_choice: Optional[str] = None,
                                 cookiefile: Optional[str] = None, cancel_event=None) -> Tuple[Optional[Dict], Optional[str]]:
    ydl_opts = {"skip_download": True, "quiet": True}
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            formats = info.get("formats") or []
            base_headers = info.get("http_headers", {})
            if format_choice == "1":
                fmt = select_audio_format(formats, quality_choice)
                if not fmt:
                    return None, "No audio format found"
                bitrate_info = f"{fmt.get('abr')}kbps" if fmt.get('abr') else "unknown"
                return {
                    "title": info.get("title", "video"),
                    "ext": fmt.get("ext", "m4a"),
                    "direct_url": fmt.get("url"),
                    "format_id": fmt.get("format_id"),
                    "bitrate": bitrate_info,
                    "vcodec": "none",
                    "acodec": fmt.get("acodec"),
                    "needs_merge": False,
                    "http_headers": fmt.get("http_headers", base_headers)
                }, None
            elif format_choice == "2":
                fmt = select_video_format(formats, quality_choice or "3")
                if not fmt:
                    return None, "No video format found"
                return {
                    "title": info.get("title", "video"),
                    "ext": fmt.get("ext", "mp4"),
                    "direct_url": fmt.get("url"),
                    "format_id": fmt.get("format_id"),
                    "resolution": f"{fmt.get('height')}p" if fmt.get('height') else "unknown",
                    "vcodec": fmt.get("vcodec"),
                    "acodec": "none",
                    "needs_merge": False,
                    "http_headers": fmt.get("http_headers", base_headers)
                }, None
            else:
                # Video+Audio format
                # IMPORTANT: For quality "3" (Best) or "2" (Medium), prefer separate streams
                # Combined formats rarely exceed 720p, so they limit quality
                quality = quality_choice or "3"

                if quality in ("2", "3"):
                    # Medium or Best quality: Try separate streams first (higher quality)
                    video_fmt = select_video_format(formats, quality)
                    audio_fmt = select_audio_format(formats, quality)

                    if video_fmt and audio_fmt:
                        # Separate streams available - use them for better quality
                        vcodec = video_fmt.get("vcodec", "")
                        acodec = audio_fmt.get("acodec", "")
                        if "av01" in vcodec or "av1" in vcodec:
                            output_ext = "mkv"
                        elif ("vp9" in vcodec or "vp09" in vcodec) and "opus" in acodec:
                            output_ext = "webm"
                        elif "vp9" in vcodec or "vp09" in vcodec or "vp8" in vcodec:
                            output_ext = "mkv"
                        else:
                            output_ext = "mp4"

                        return {
                            "title": info.get("title", "video"),
                            "ext": output_ext,
                            "video_url": video_fmt.get("url"),
                            "audio_url": audio_fmt.get("url"),
                            "video_ext": video_fmt.get("ext", "mp4"),
                            "audio_ext": audio_fmt.get("ext", "m4a"),
                            "vcodec": video_fmt.get("vcodec"),
                            "acodec": audio_fmt.get("acodec"),
                            "resolution": f"{video_fmt.get('height')}p" if video_fmt.get('height') else "unknown",
                            "needs_merge": True,
                            "http_headers": video_fmt.get("http_headers", base_headers)
                        }, None
                    else:
                        # Fallback to combined format if separate streams not available
                        fmt = select_combined_format(formats, quality)
                        if fmt:
                            return {
                                "title": info.get("title", "video"),
                                "ext": fmt.get("ext", "mp4"),
                                "direct_url": fmt.get("url"),
                                "format_id": fmt.get("format_id"),
                                "resolution": f"{fmt.get('height')}p" if fmt.get('height') else "unknown",
                                "vcodec": fmt.get("vcodec"),
                                "acodec": fmt.get("acodec"),
                                "needs_merge": False,
                                "http_headers": fmt.get("http_headers", base_headers)
                            }, None
                        else:
                            return None, "Cannot find suitable video/audio streams"
                else:
                    # Low quality: Combined format is fine (smaller, faster)
                    fmt = select_combined_format(formats, quality)
                    if fmt:
                        return {
                            "title": info.get("title", "video"),
                            "ext": fmt.get("ext", "mp4"),
                            "direct_url": fmt.get("url"),
                            "format_id": fmt.get("format_id"),
                            "resolution": f"{fmt.get('height')}p" if fmt.get('height') else "unknown",
                            "vcodec": fmt.get("vcodec"),
                            "acodec": fmt.get("acodec"),
                            "needs_merge": False,
                            "http_headers": fmt.get("http_headers", base_headers)
                        }, None
                    else:
                        # Fallback to separate streams
                        video_fmt = select_video_format(formats, quality)
                        audio_fmt = select_audio_format(formats, quality)
                        if not video_fmt or not audio_fmt:
                            return None, "Cannot find suitable video/audio streams"

                        vcodec = video_fmt.get("vcodec", "")
                        acodec = audio_fmt.get("acodec", "")
                        output_ext = "mp4"
                        if "av01" in vcodec or "av1" in vcodec:
                            output_ext = "mkv"
                        elif ("vp9" in vcodec or "vp09" in vcodec) and "opus" in acodec:
                            output_ext = "webm"
                        elif "vp9" in vcodec or "vp09" in vcodec or "vp8" in vcodec:
                            output_ext = "mkv"

                        return {
                            "title": info.get("title", "video"),
                            "ext": output_ext,
                            "video_url": video_fmt.get("url"),
                            "audio_url": audio_fmt.get("url"),
                            "video_ext": video_fmt.get("ext", "mp4"),
                            "audio_ext": audio_fmt.get("ext", "m4a"),
                            "vcodec": video_fmt.get("vcodec"),
                            "acodec": audio_fmt.get("acodec"),
                            "resolution": f"{video_fmt.get('height')}p" if video_fmt.get('height') else "unknown",
                            "needs_merge": True,
                            "http_headers": video_fmt.get("http_headers", base_headers)
                        }, None
    except Exception as e:
        return None, str(e)
