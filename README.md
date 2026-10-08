# YouTube Playlist Downloader

A highly robust, parallel-processing YouTube downloader with a modern GUI, smart IDM integration, and a completely bulletproof yt-dlp native core to bypass YouTube's 403 Forbidden errors.

## Why This Downloader is Different (and Better)

Normal YouTube download scripts and wrappers often fail today because YouTube aggressively blocks third-party downloads with 403 Forbidden errors, limits speeds, and requires complex bot-bypasses. Here is how this tool solves everything:

1. **Bulletproof 403 Bypass:** Unlike normal scripts that extract a URL and pass it to 
equests (which gets instantly blocked by YouTube), this app uses **yt-dlp native downloading** internally. It automatically uses YouTube Android VR and iOS client spoofing to ensure your downloads never fail.
2. **Multi-Part Native Downloads (Concurrent Fragments):** Standard wrappers download videos in a slow, single-threaded connection. We configured the engine to use **8 concurrent connections per video** (Multi-Part Download), acting exactly like IDM to saturate your bandwidth!
3. **Smart IDM Integration:** Have Internet Download Manager? The app detects it and offloads the heavy lifting to IDM while handling the extraction quietly in the background.
4. **Parallel Video Downloads:** Not only does it download a single video in 8 chunks, it also downloads **multiple videos at the same time** (configurable batch size) using a thread pool.
5. **Modern CustomTkinter GUI:** Forget ugly command-line scripts. Enjoy a sleek, dark-themed dashboard showing live speeds, ETAs, and individual progress bars for every concurrent video.
6. **Graceful Cancellation:** Hit "Cancel" anytime. It instantly kills download threads, stops FFmpeg merging, and cleans up without leaving zombie processes.
7. **Lossless Merging:** Automatically downloads the highest quality Video and Audio streams separately and merges them losslessly using FFmpeg.

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
- **Multi-Part Native Downloading:** 
  - Each video uses up to **8 concurrent connections/fragments** natively via the yt-dlp engine.
  - No slow single-threaded limits; acts like IDM to max out your internet speed.
- **Bulletproof Execution:** Bypasses 403 Forbidden errors by using internal Android/iOS client APIs.
- Shows per-file progress bars with live speed and ETA tracking.
- If a video requires separate streams (e.g. 1080p+), it downloads both sequentially (each in 8 parts) and merges via FFmpeg (lossless).
- Waits a configurable number of minutes between batches (Fast/Medium/Slow profiles) to avoid YouTube rate-limiting.
- GUI shows individual progress cards for each file being downloaded simultaneously.
  - Real-time status updates and clean UI.

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
