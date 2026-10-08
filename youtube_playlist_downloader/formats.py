#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Format selection helpers for audio/video/combined."""

from typing import Dict, List, Optional


def select_audio_format(formats: List[Dict], quality_choice: Optional[str] = None) -> Optional[Dict]:
    candidates = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none" and f.get("url")]
    if not candidates:
        return None

    # Helper function to score audio quality
    def audio_quality_score(fmt):
        abr = fmt.get("abr") or 0
        asr = fmt.get("asr") or 44100  # Sample rate
        # Prefer Opus > AAC > MP3 for better quality at same bitrate
        codec_bonus = 0
        acodec = fmt.get("acodec", "")
        if "opus" in acodec:
            codec_bonus = 1.15  # Opus is significantly better
        elif "aac" in acodec or "mp4a" in acodec:
            codec_bonus = 1.05
        # Score: bitrate with codec multiplier, then sample rate
        return (abr * codec_bonus, asr)

    if quality_choice == "1":
        # Low quality: ≤64kbps
        filt = [f for f in candidates if (f.get("abr") or 0) <= 64]
        if filt:
            # Among low quality, prefer highest in range
            filt.sort(key=lambda x: -(x.get("abr") or 0))
            return filt[0]
        # Fallback to lowest available
        candidates.sort(key=lambda x: (x.get("abr") or 0))
        return candidates[0]
    elif quality_choice == "2":
        # Medium quality: 96-128kbps
        filt = [f for f in candidates if 96 <= (f.get("abr") or 0) <= 128]
        if filt:
            filt.sort(key=audio_quality_score, reverse=True)
            return filt[0]
        # Fallback to closest to 128kbps
        candidates.sort(key=lambda x: abs((x.get("abr") or 0) - 128))
        return candidates[0]
    else:
        # Best quality: highest bitrate with best codec
        candidates.sort(key=audio_quality_score, reverse=True)
        return candidates[0]


def select_video_format(formats: List[Dict], quality_choice: str) -> Optional[Dict]:
    candidates = [f for f in formats if f.get("acodec") == "none" and f.get("vcodec") != "none" and f.get("url")]
    if not candidates:
        return None

    # Helper function to score format quality
    def quality_score(fmt):
        height = fmt.get("height") or 0
        fps = fmt.get("fps") or 30
        tbr = fmt.get("tbr") or 0
        vbr = fmt.get("vbr") or 0
        # Prefer VP9/AV1 over AVC for better compression at same quality
        codec_bonus = 0
        vcodec = fmt.get("vcodec", "")
        if "vp9" in vcodec or "vp09" in vcodec:
            codec_bonus = 0.1
        elif "av01" in vcodec or "av1" in vcodec:
            codec_bonus = 0.2
        # Score: prioritize resolution, then bitrate, then fps, then codec
        return (height * (1 + codec_bonus), vbr or tbr, fps)

    if quality_choice == "1":
        # Low quality: ≤360p, prefer lowest height that's still watchable
        filt = [f for f in candidates if (f.get("height") or 0) <= 360]
        if filt:
            filt.sort(key=lambda x: (x.get("height") or 0))
            return filt[0]
        # Fallback to lowest available
        candidates.sort(key=lambda x: (x.get("height") or 0))
        return candidates[0]
    elif quality_choice == "2":
        # Medium quality: 480p-720p, prefer highest in range
        filt = [f for f in candidates if 480 <= (f.get("height") or 0) <= 720]
        if filt:
            filt.sort(key=quality_score, reverse=True)
            return filt[0]
        # Fallback to closest match
        candidates.sort(key=lambda x: abs((x.get("height") or 0) - 720))
        return candidates[0]
    else:
        # Best quality: highest resolution, best bitrate, best codec
        candidates.sort(key=quality_score, reverse=True)
        return candidates[0]


def select_combined_format(formats: List[Dict], quality_choice: str) -> Optional[Dict]:
    candidates = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") != "none" and f.get("url")]
    if not candidates:
        return None

    # Helper function to score combined format quality
    def quality_score(fmt):
        height = fmt.get("height") or 0
        fps = fmt.get("fps") or 30
        tbr = fmt.get("tbr") or 0
        vbr = fmt.get("vbr") or 0
        abr = fmt.get("abr") or 0
        # Prefer better codecs
        codec_bonus = 0
        vcodec = fmt.get("vcodec", "")
        if "vp9" in vcodec or "vp09" in vcodec:
            codec_bonus = 0.1
        elif "av01" in vcodec or "av1" in vcodec:
            codec_bonus = 0.2
        # Score: prioritize resolution, then bitrate, then fps
        return (height * (1 + codec_bonus), vbr or tbr or (abr * 1.5), fps)

    if quality_choice == "1":
        # Low quality: ≤360p
        filt = [f for f in candidates if (f.get("height") or 0) <= 360]
        if filt:
            filt.sort(key=lambda x: (x.get("height") or 0))
            return filt[0]
        candidates.sort(key=lambda x: (x.get("height") or 0))
        return candidates[0]
    elif quality_choice == "2":
        # Medium quality: 480p-720p
        filt = [f for f in candidates if 480 <= (f.get("height") or 0) <= 720]
        if filt:
            filt.sort(key=quality_score, reverse=True)
            return filt[0]
        # Fallback to closest match
        candidates.sort(key=lambda x: abs((x.get("height") or 0) - 720))
        return candidates[0]
    else:
        # Best quality: highest resolution and bitrate
        candidates.sort(key=quality_score, reverse=True)
        return candidates[0]
