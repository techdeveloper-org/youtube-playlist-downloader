#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Main entrypoint for youtube_playlist_downloader package"""

import os
import sys

from utils import now, CANCEL_EVENT
from choices import choose_auto_or_manual, get_download_speed_config, get_user_choices, get_download_method, check_cookies
from extractor import extract_playlist_info
from files_io import save_urls_to_file, load_urls_from_file
from speedtest_utils import measure_network_speed_ookla, measure_network_speed, auto_select_settings
from paths import find_idm
from workflow import process_batch_idm_with_monitoring, process_batches_normal


def main():
    print("=" * 60)
    print("🔗 Smart YouTube Playlist Downloader -> IDM or Normal")
    print("   with Speed Management and Progress Bars")
    print("=" * 60)

    playlist_urls_input = input("\nEnter YouTube playlist/video URL(s) (comma-separated for multiple): ").strip()
    # Split by comma and clean up whitespace
    playlist_urls = [url.strip() for url in playlist_urls_input.split(',') if url.strip()]

    if not playlist_urls:
        print(f"[{now()}] ❌ No valid URLs provided.")
        sys.exit(1)

    output_base = input("Enter base output folder path: ").strip()
    output_base = os.path.abspath(output_base)
    os.makedirs(output_base, exist_ok=True)

    # Choose Auto or Manual selection for settings
    if choose_auto_or_manual():
        print(f"[{now()}] ⏳ Measuring your internet speed, please wait…")
        mbps = measure_network_speed_ookla()
        if mbps is None:
            print(f"[{now()}] ⏳ Falling back to HTTP test… please wait")
            mbps = measure_network_speed()
        wait_time, short_delay, use_random, format_choice, quality_choice, method = auto_select_settings(mbps)
    else:
        wait_time, short_delay, use_random = get_download_speed_config()
        format_choice, quality_choice = get_user_choices()
        method = get_download_method()  # "1" IDM, "2" Normal

    # Fallback if IDM not present for IDM selection
    if method == "1" and not find_idm():
        print(f"[{now()}] ⚠️ IDM not found. Falling back to Normal (Python).")
        method = "2"
    elif method == "1":
        print(f"[{now()}] ✅ Using IDM for downloads (found at: {find_idm()})")
    else:
        print(f"[{now()}] ✅ Using Normal Python mode for downloads")

    cookies_file = os.path.join(output_base, "yt_cookies.txt")
    check_cookies(cookies_file)

    # Process each playlist/video URL
    total_playlists = len(playlist_urls)
    all_failed_videos = []

    for playlist_idx, playlist_url in enumerate(playlist_urls, start=1):
        if CANCEL_EVENT.is_set():
            break

        print(f"\n{'='*60}")
        print(f"[{now()}] 📥 Processing URL {playlist_idx}/{total_playlists}")
        print(f"{'='*60}")

        # Extract URLs
        print(f"[{now()}] 📥 STEP 1: Extracting video URLs…")
        try:
            playlist_title, all_video_urls = extract_playlist_info(playlist_url)
        except Exception as e:
            print(f"[{now()}] ❌ Failed to extract info from {playlist_url}: {e}")
            continue

        safe_title = ''.join(c for c in playlist_title if c.isalnum() or c in ' -_().[]').rstrip()
        # For multiple playlists, create unique folder names
        if total_playlists > 1:
            playlist_folder = os.path.join(output_base, f"{playlist_idx}_{safe_title}")
        else:
            playlist_folder = os.path.join(output_base, safe_title)
        os.makedirs(playlist_folder, exist_ok=True)

        urls_file = os.path.join(playlist_folder, "urls.txt")
        unavailable_file = os.path.join(playlist_folder, "unavailable_videos.txt")

        if not os.path.exists(urls_file):
            save_urls_to_file(all_video_urls, urls_file)
        else:
            print(f"[{now()}] 📄 Using existing URL list from: {urls_file}")

        video_urls = load_urls_from_file(urls_file)

        print(f"\n🎬 {('Playlist' if len(all_video_urls) > 1 else 'Video')}: '{playlist_title}'")
        print(f"📊 Videos Remaining: {len(video_urls)}")
        print(f"[{now()}] ✅ URL extraction complete!")

        # STEP 2: Download
        print(f"\n{'='*60}")
        print(f"[{now()}] 🚀 STEP 2: Starting downloads for '{playlist_title}'…")
        print(f"{'='*60}")

        try:
            if method == "1":
                failed_videos = process_batch_idm_with_monitoring(
                    video_urls, format_choice, quality_choice,
                    cookies_file, playlist_folder, urls_file,
                    wait_time, short_delay, use_random,
                    batch_size=5  # Default batch size for CLI
                )
            else:
                failed_videos = process_batches_normal(
                    video_urls, format_choice, quality_choice,
                    cookies_file, playlist_folder, urls_file,
                    wait_time, use_random,
                    batch_size=5  # Default batch size for CLI
                )
        except KeyboardInterrupt:
            CANCEL_EVENT.set()
            print(f"\n[{now()}] ⛔ Canceled by user. In-flight downloads will stop shortly…")
            failed_videos = []

        # Save unavailable videos
        if failed_videos:
            with open(unavailable_file, "a", encoding="utf-8") as uf:
                for v in failed_videos:
                    uf.write(f"{v}  # Failed after retry\n")
            print(f"\n[{now()}] ⚠️ {len(failed_videos)} videos failed for '{playlist_title}' and saved to: {unavailable_file}")
            all_failed_videos.extend(failed_videos)

        if CANCEL_EVENT.is_set():
            break

        # Add separator between playlists
        if playlist_idx < total_playlists:
            print(f"\n{'='*60}")
            print(f"[{now()}] ✅ Completed playlist {playlist_idx}/{total_playlists}: '{playlist_title}'")
            print(f"[{now()}] 📋 Moving to next playlist...")
            print(f"{'='*60}")

    if CANCEL_EVENT.is_set():
        print(f"\n{'='*60}")
        print(f"[{now()}] ⛔ Canceled. You can rerun later to resume from 'urls.txt'.")
        print(f"{'='*60}\n")
        return

    print(f"\n{'='*60}")
    print(f"[{now()}] ✅ All done!")
    if total_playlists > 1:
        print(f"[{now()}] 📊 Processed {total_playlists} playlists/videos")
    if all_failed_videos:
        print(f"[{now()}] ⚠️ Total failed videos across all playlists: {len(all_failed_videos)}")
    print(f"{'='*60}")
    print(f"💡 Tip: To resume later, rerun the script. It will pick up remaining URLs from 'urls.txt'")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
