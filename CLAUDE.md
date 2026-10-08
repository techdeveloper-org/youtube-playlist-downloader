# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a YouTube playlist downloader for Windows that intelligently downloads videos using either IDM (Internet Download Manager) or Python's requests library. The tool auto-detects network speed and selects optimal download settings, supports resumable downloads, and handles video+audio stream merging via FFmpeg.

## Running the Application

### GUI Mode (Recommended)
```bash
python run_gui.py
```

### CLI Mode
**Primary method:**
```bash
python -m youtube_playlist_downloader
```

**Alternative method:**
```bash
python run_youtube_downloader.py
```

The application requires:
- Python 3.9+
- FFmpeg in PATH (for stream merging)
- IDM (optional, auto-detected if available)

Dependencies are auto-installed on first run:
- yt-dlp
- requests
- tqdm
- speedtest-cli
- customtkinter (for GUI mode)

## Architecture

### Core Flow (main.py)

1. **User Input**: Collects playlist/video URL(s) (comma-separated for multiple) and output folder
2. **Mode Selection**: Auto-select (speed-based) or Manual configuration
3. **Speed Testing** (Auto mode only): Ookla speedtest → HTTP fallback if needed
4. **Auto Selection Logic** (`speedtest_utils.py`):
   - ≤1 Mbps → Low quality, Slow profile (12 min wait)
   - 1-10 Mbps → Medium quality, Medium profile (8 min wait)
   - >10 Mbps → High quality, Fast profile (5 min wait)
   - Auto-selects IDM if available, else Python mode
5. **Playlist Extraction**: yt-dlp extracts all video URLs → saves to `urls.txt`
   - Supports both playlists and individual video URLs
   - Auto-detects URL type (playlist vs single video)
6. **Batch Downloads**: Processes videos in user-configurable batches (default 5) with wait times between batches
   - Each video uses 4-6 parallel chunks in batch mode (prevents connection exhaustion)
   - Single file downloads use 8-16 chunks for maximum speed

### Module Responsibilities

**Extraction & Format Selection:**
- `extractor.py`: Playlist/video URL extraction and direct download info via yt-dlp
  - `is_playlist_url()`: Detects if URL is playlist or single video
  - Supports comma-separated multiple URLs (playlists or individual videos)
  - **Smart format priority**: For Best/Medium quality, prefers separate streams over combined formats
    - Combined formats max out at 720p on YouTube
    - Separate streams allow true highest quality (up to 4K/8K)
  - **Intelligent container selection**: mkv/webm/mp4 based on codec (AV1→mkv, VP9+Opus→webm, H.264→mp4)
- `formats.py`: Audio/video/combined format selection with **intelligent quality scoring**
  - Removed hardcoded format IDs, uses dynamic scoring system
  - Audio: Low (≤64kbps), Medium (96-128kbps), Best (highest) + codec bonuses (Opus>AAC)
  - Video: Low (≤360p), Medium (480p-720p), Best (highest) + resolution, bitrate, fps, codec scoring

**Download Workflows:**
- `workflow.py`: Orchestrates IDM and Normal mode batch processing
  - IDM: Sequential processing with IDM queue + merge when needed
  - Normal: Concurrent downloads (user-configurable batch size, default 5) with ThreadPoolExecutor
- `downloaders.py`: Core download implementations with **chunked parallel downloads**
  - `add_to_idm()`: Spawns IDM process with `/d /p /f /n` flags
  - `download_chunk()`: Downloads single chunk using HTTP byte-range requests
  - `download_file_with_progress()`: Python download with **multi-connection chunked download** (IDM-style)
    - Uses 4-16 parallel chunks per file based on size and batch parallelism
    - Background thread for smooth progress updates every 0.3s
    - Shows active/completed chunk counts: `[Active: X/Y | Done: Z/Y]`
    - Smart fallback to sequential download if server doesn't support ranges
  - `download_and_merge_with_progress()`: Downloads separate video+audio streams with chunks, merges with FFmpeg

**Supporting Utilities:**
- `speedtest_utils.py`: Network speed measurement (Ookla + HTTP fallback) and auto-selection mapping
- `choices.py`: User prompts for manual mode (format, quality, method, speed profile)
- `paths.py`: `find_idm()` searches PATH and common install dirs for idman.exe
- `files_io.py`: Read/write/remove URLs from urls.txt
- `utils.py`: Timestamps, filename sanitization, cookie validation, sleep with cancel support
- `deps.py`: Auto-install/import dependencies on first run
- `gui.py`: Modern CustomTkinter GUI with real-time progress tracking and log display

### State Management

- **urls.txt**: Tracks remaining videos to download (enables resume)
- **unavailable_videos.txt**: Failed downloads after retry
- **yt_cookies.txt**: YouTube authentication cookies (placed in output folder)
- **CANCEL_EVENT**: Global threading.Event for graceful Ctrl+C handling

### Download Modes

**IDM Mode** (`method == "1"`):
- Calls `idman.exe /d <url> /p <folder> /f <filename> /n`
- If video needs merge (separate streams): downloads both via Python, merges with FFmpeg
- Sequential processing with short delays (2-5s) between adds

**Normal Mode** (`method == "2"`):
- ThreadPoolExecutor with user-configurable concurrent workers per batch (default 5)
- **Chunked parallel downloads** (IDM-style multi-connection):
  - Each file downloads using 4-6 parallel chunks in batch mode
  - HTTP byte-range requests for concurrent chunk downloads
  - Background thread updates progress every 0.3s for smooth UI
  - Shows `[Active: X/Y | Done: Z/Y]` chunk status
  - Automatic fallback to sequential if server doesn't support ranges
- Streaming downloads with live progress bars (MB/GB and Mbps)
- Handles merging transparently when needed with lossless FFmpeg

## Cookie Management

Place `yt_cookies.txt` in the output folder for age-restricted/private videos. The tool checks cookie staleness and prompts for updates if needed. Cookie validation looks for specific error patterns in yt-dlp output.

## Error Handling & Resume

- Failed videos are retried once, then logged to `unavailable_videos.txt`
- Ctrl+C triggers graceful shutdown: sets CANCEL_EVENT, cleans partial files
- Resume: Rerun the script, it reads remaining URLs from `urls.txt`

## FFmpeg Merging (Lossless)

When separate video+audio streams are required:
1. Downloads to temp files in system temp directory
2. Merges with: `ffmpeg -y -i video -i audio -c:v copy -c:a copy output.mp4`
   - Both video and audio use `copy` codec for **lossless merging** (no re-encoding)
3. Cleans up temp files on success or failure

## GUI Architecture (`gui.py`)

The GUI is built with CustomTkinter and follows a clean threading model with a two-panel layout:

**Layout Structure (1200x800):**
- **Left Panel (Settings)**: Scrollable frame with all configuration options
  - Title and branding
  - Playlist URL input field (supports comma-separated multiple URLs)
  - Output folder selection with browse button (📁)
  - Mode selection (Auto/Manual radio buttons)
  - Manual settings frame (collapsible): Speed profile, format, quality, method, batch size, random delays
  - Batch size control: User-configurable (default 5) for parallel downloads
  - Control buttons: Start Download (green) / Cancel (red)
  - Scrollbar for overflow content

- **Right Panel (Progress & Logs)**: Grid layout with 3 sections
  - Overall progress: Shows "X / Y videos (Z%)" with progress bar
  - Individual files progress: Scrollable frame with per-file progress cards
    - Each file gets its own card with: filename, progress bar, status text
    - Cards are dynamically added/updated/removed during download
    - Shows real-time download progress with chunk status: "45.2 MB/100 MB at 8.5 Mbps [Active: 4/6]"
    - Statistics bar: "Total: X | Pending: Y | Downloading: Z | Completed: W"
  - Logs section: Compact scrollable text area at bottom with auto-scroll

**Threading & Communication:**
- `download_worker()`: Runs in separate daemon thread
- `log_queue`: Thread-safe queue for log messages from backend → GUI
- `progress_queue`: Thread-safe queue for progress updates with enhanced data:
  - `current`, `total`: Overall video counts
  - `file_id`: Unique identifier for each file
  - `current_file`: Filename being downloaded
  - `percent`: Download percentage (0-100)
  - `status`: Status text (e.g., "Downloading...", "45.2 MB/100 MB")
  - `completed`: Flag to remove file card when done
- `update_log_display()`: Polls log_queue every 100ms
- `update_progress_display()`: Polls progress_queue every 100ms, manages file cards

**Individual File Progress Management:**
- `add_file_progress(file_name, file_id)`: Creates new progress card for file
- `update_file_progress(file_id, percent, status)`: Updates specific file's progress
- `remove_file_progress(file_id)`: Removes completed file card
- `file_progress_widgets`: Dict storing all active file progress widgets

**Progress Callback Integration:**
- GUI passes `progress_callback=self.update_progress` to workflow functions
- `workflow.py` functions accept optional `progress_callback` parameter
- Callbacks send: `current`, `total`, `file_id`, `current_file`, `percent`, `status`, `completed`
- Each file gets unique `file_id` for tracking individual progress

## Key Design Patterns

- **Auto-dependency installation**: deps.py checks and installs missing packages at import time
- **Chunked parallel downloads**: IDM-style multi-connection downloads using HTTP byte-range requests
  - 4-6 chunks per file in batch mode (prevents connection exhaustion with multiple videos)
  - 8-16 chunks for single file downloads (maximum speed)
  - Adaptive chunk sizing based on file size and batch parallelism
  - Background progress thread for smooth UI updates (polls every 0.3s)
- **Progress tracking**: All downloads show unified progress format: `[downloaded/total at: X.XX Mbps] [Active: X/Y | Done: Z/Y]`
- **Fallback logic**:
  - IDM → Normal mode if IDM not found
  - Ookla → HTTP mirrors for speed testing
  - Combined format → separate streams for Best/Medium quality (ensures highest quality)
  - Chunked download → sequential if server doesn't support byte ranges
- **Batch throttling**: Waits between batches (Fast/Medium/Slow) with optional randomization to avoid rate limits
- **Lossless merging**: FFmpeg uses `-c:v copy -c:a copy` to avoid re-encoding (no quality loss)
- **Thread-safe GUI updates**: Queue-based communication between worker threads and UI thread
- **Smart quality selection**: Scoring system evaluates resolution, bitrate, fps, codec quality (no hardcoded format IDs)
