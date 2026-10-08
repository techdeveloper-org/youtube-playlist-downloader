# YouTube Playlist Downloader (IDM + Python)

A smart YouTube playlist downloader for Windows that can:
- Extract videos from YouTube playlists **or individual video URLs** (supports comma-separated multiple URLs)
- Download via IDM (Internet Download Manager) or Normal (Python requests with **IDM-style multi-connection**)
- **Chunked parallel downloads**: Each file uses 4-16 concurrent connections for maximum speed
- Auto-detect your internet speed and choose the best download settings
- Auto-select Video+Audio quality based on speed (≤1 Mbps → Low, ≤10 Mbps → Medium, >10 Mbps → High)
  - **Intelligent quality selection**: Ensures true highest quality (separate streams preferred for Best/Medium)
  - Combined formats limited to 720p on YouTube; separate streams allow up to 4K/8K
- Show per-file progress bars with live MB/GB, Mbps, and **chunk status** [Active: X/Y | Done: Z/Y]
- Merge separate video and audio streams with **lossless FFmpeg** (no re-encoding)
- User-configurable batch downloads (default 5 at a time) with wait times between batches
- Resume unfinished downloads using urls.txt
- Gracefully cancel with Ctrl+C (immediate stop)

This repository organizes the logic into a clean, maintainable Python package.

---

## Features

- **Auto Select mode** (recommended)
  - Uses Ookla Speedtest (speedtest-cli) to measure your real download speed
  - Falls back to HTTP mirror test if Ookla fails
  - Picks quality automatically:
    - ≤1 Mbps → Video+Audio Low
    - ≤10 Mbps → Video+Audio Medium
    - >10 Mbps → Video+Audio High
  - Chooses IDM if installed (preferred on moderate+ links), otherwise Normal (Python)
  - Selects a conservative batch wait profile based on speed

- **Manual Mode**
  - Choose speed profile (Fast/Medium/Slow), with optional randomized waits
  - Choose format and quality
  - Choose download method (IDM or Normal)
  - Configure batch size (how many videos download in parallel, default 5)

- **Progress tracking** (GUI & CLI)
  - GUI:
    - Overall progress bar showing total completion percentage
    - Individual file progress cards with real-time updates
    - Each file displayed separately with its own progress bar and chunk status
    - Shows: "45.2 MB/100 MB at 8.5 Mbps [Active: 4/6]" (active chunks out of total)
    - Statistics bar: "Total: X | Pending: Y | Downloading: Z | Completed: W"
    - Cards dynamically added/removed during download
  - CLI: Per-file progress bars with "downloaded/total at: X.XX Mbps [Active: X/Y | Done: Z/Y]"
  - IDM merges (when separate streams): same rich progress display with chunk tracking
  - Clear messages like "please wait…" during speed testing and applying choices

- **Robustness**
  - Auto-installs dependencies (yt-dlp, requests, tqdm, speedtest-cli, customtkinter)
  - Dynamic IDM detection (no hardcoded path)
  - **Intelligent quality selection**: No hardcoded format IDs, uses dynamic scoring (resolution, bitrate, fps, codec)
  - **Smart format priority**: Separate streams for Best/Medium quality (ensures true highest quality, not limited to 720p)
  - **Chunked parallel downloads**: 4-6 chunks per file in batch mode, 8-16 for single files
    - HTTP byte-range requests for concurrent downloads
    - Automatic fallback to sequential if server doesn't support ranges
  - Cookie file checks with friendly prompts
  - Retry for failed items; write failures to `unavailable_videos.txt`
  - Graceful cancellation; cleans up partial files, immediate stop when canceled
  - **Lossless merging**: FFmpeg uses `-c:v copy -c:a copy` (no re-encoding, no quality loss)

---

## Requirements & Installation

- Windows (PowerShell or Command Prompt)
- Python 3.9+
- FFmpeg available in PATH (for lossless merging of high quality video+audio)
- IDM (optional) — auto-detected if installed; otherwise falls back to Python multi-connection mode

### Installation

```bash
# Clone the repository and navigate into it
git clone <repo-url>
cd youtube-playlist-downloader

# Install dependencies
pip install -r requirements.txt

# Or install as an editable package with CLI commands
pip install -e .
```

---

## Project Structure

```
youtube-playlist-downloader/
├── .gitignore                 # Git ignore for caches, venvs, IDE configs, downloads
├── requirements.txt           # Standard Python dependencies
├── pyproject.toml             # Modern PEP 621 package metadata & entry points
├── README.md                  # Project documentation
├── CLAUDE.md                  # Claude Code guidance & technical reference
├── run_gui.py                 # Direct GUI launcher script
├── run_youtube_downloader.py  # Direct CLI launcher script
└──  # Core Python package
    ├── __init__.py
    ├── __main__.py            # Enables `python main.py`
    ├── deps.py                # Dependency check/importer
    ├── utils.py               # Helpers: time, sanitize, human_bytes, TTS, cancel, cookies
    ├── files_io.py            # URL file persistence & cleanup
    ├── paths.py               # IDM detection logic
    ├── formats.py             # Format scoring & stream selection
    ├── extractor.py           # Video/playlist metadata extraction (yt-dlp)
    ├── downloaders.py         # Multi-connection chunked downloads & FFmpeg merge
    ├── speedtest_utils.py     # Ookla + HTTP fallback network speed test
    ├── choices.py             # Interactive CLI selection prompts
    ├── workflow.py            # Sequential & concurrent batch processing
    ├── main.py                # CLI execution engine
    └── gui.py                 # CustomTkinter modern graphical user interface
```

---

## Usage

### GUI Mode (Recommended)

**Launch the modern graphical interface:**
```bash
python run_gui.py
```

The GUI provides:
- 🎨 **Modern two-panel layout** (1200x800) with dark theme
- **Left Panel - Settings** (Scrollable):
  - 📋 Playlist/Video URL input (supports **comma-separated multiple URLs**)
  - 📂 Output folder selection with browse button
  - 🧠 Auto/Manual mode selection
  - ⚙️ Collapsible manual settings (Speed, Format, Quality, Method, **Batch Size**, Delays)
  - 📦 **Batch size control**: Configure how many videos download in parallel (default 5)
  - 🚀 Start/Cancel buttons (green/red)
- **Right Panel - Progress & Logs**:
  - 📊 **Overall progress bar** with "X / Y videos (Z%)"
  - 📁 **Individual file progress cards** (scrollable):
    - Each file shows: name, progress bar, **chunk status**
    - Real-time updates: "45.2 MB/100 MB at 8.5 Mbps [Active: 4/6]"
    - Statistics: "Total: X | Pending: Y | Downloading: Z | Completed: W"
    - Multiple files download simultaneously (up to batch size)
    - Cards auto-remove when completed
  - 📝 **Live logs section** at bottom with auto-scroll

### CLI Mode

**Step 1:** Run one of these from PowerShell:

- As a module (recommended):
```bash
python main.py
```

- Or via the launcher script:
```bash
python run_youtube_downloader.py
```

**Step 2:** Paste YouTube playlist/video URL(s) (comma-separated for multiple) and choose an output folder.

**Step 3:** Choose "Auto select" (recommended) or Manual.
   - Auto Mode will measure your speed and select:
     - Method: IDM (if installed) or Normal (Python)
     - Quality: Video+Audio Low/Medium/High based on speed
     - Wait profile (Fast/Medium/Slow)
   - You'll see "please wait" messages while speed test runs and options are applied.

**Step 4:** The tool extracts playlist URLs, writes them to `urls.txt` under the playlist folder, and starts batch downloads.

**Step 5:** To resume later, simply rerun. It reads remaining URLs from `urls.txt`.

**Step 6:** To cancel anytime, press Ctrl+C. In-flight downloads stop gracefully and partial files are cleaned up where possible.

---

## Cookies (YouTube auth)

If your playlist or videos require authentication (e.g., age-restricted/private), export your YouTube cookies and save them to:
```
<your_output_folder>\yt_cookies.txt
```
If missing/stale, the tool will prompt with clear instructions. You can update the cookie file and continue.

---

## IDM Integration

- The tool dynamically locates IDM (idman.exe):
  - Searches PATH (which idman.exe)
  - Looks in common install locations (Program Files / Program Files (x86))
- When IDM is selected (or Auto picks it), each single-URL download is queued in IDM.
- If a video requires separate video+audio streams, the tool downloads both and merges via FFmpeg — with progress.
- If IDM isn’t found, the tool automatically falls back to Normal (Python) mode.

---

## Normal (Python) Mode

- Downloads up to **user-configured batch size** (default 5) items concurrently per batch
- **Chunked parallel downloads** (IDM-style multi-connection):
  - Each file uses 4-6 parallel chunks in batch mode (prevents connection exhaustion)
  - Single file downloads use 8-16 chunks for maximum speed
  - HTTP byte-range requests for concurrent chunk downloads
  - Background thread updates progress every 0.3s for smooth UI
  - Shows chunk status: `[Active: X/Y | Done: Z/Y]`
  - Automatic fallback to sequential if server doesn't support byte ranges
- Shows per-file progress bars with live Mbps and chunk tracking
- If a video requires separate streams, shows a combined progress bar and merges via FFmpeg (lossless - no re-encoding)
- Waits a configurable number of minutes between batches (Fast/Medium/Slow profiles)
- GUI shows individual progress cards for each file being downloaded simultaneously
  - Each concurrent download gets its own card with progress bar
  - Real-time status updates: "45.2 MB/100 MB at 8.5 Mbps [Active: 4/6]"
  - Statistics bar: "Total: X | Pending: Y | Downloading: Z | Completed: W"
  - Cards are removed automatically when files complete

---

## Troubleshooting

**FFmpeg not found**
- Ensure `ffmpeg.exe` is in your PATH. Install from https://ffmpeg.org/ or a package manager.

**Speed test too slow/wrong**
- The tool uses Ookla Speedtest (multi-threaded) when available
- If Ookla fails, it tries multiple HTTP mirrors and takes the maximum
- If your result still looks wrong, run again; internet conditions or mirror congestion can vary

**IDM is installed but not detected**
- Make sure `idman.exe` is in PATH or installed in the default directory (Internet Download Manager)

**Stuck or you want to stop**
- Press Ctrl+C (CLI) or Cancel button (GUI) to stop **immediately**
- Downloads stop within seconds, partial files are cleaned up

**Resume later**
- Just rerun the script; it respects `urls.txt` in the playlist folder

---

## Development

For developers working on this codebase, see [CLAUDE.md](CLAUDE.md) for detailed architecture documentation, module responsibilities, and design patterns.

---

## Notes

- Windows-focused implementation; tested with PowerShell on Windows
- Console output includes status emojis; they are purely informational

---

## License

MIT License

## v2.0.0 Migration Note
In version 2.0.0, all core Python modules have been flattened and moved directly to the repository root.
The old `youtube_playlist_downloader` namespace is deprecated and will be removed in v3.0.0.
Please use `python main.py` or `python run_youtube_downloader.py` directly, and import root modules (e.g., `import utils` instead of `from youtube_playlist_downloader import utils`).
