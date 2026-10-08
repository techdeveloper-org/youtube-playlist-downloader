#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Modern GUI for YouTube Playlist Downloader using CustomTkinter (View Layer)"""

import sys
import subprocess
import os
import queue

# Auto-install customtkinter if not present
try:
    import customtkinter as ctk
except ImportError:
    print("Installing customtkinter...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "customtkinter"])
    import customtkinter as ctk

from tkinter import filedialog, messagebox
from typing import Optional, Dict

from model import DownloadConfig
from utils import now

class DownloaderView:
    def __init__(self, root: ctk.CTk, controller):
        self.root = root
        self.controller = controller
        
        # Set appearance mode and color theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root.title("YouTube Playlist Downloader")
        self.root.geometry("1200x800")

        # Variables
        self.playlist_url_var = ctk.StringVar()
        self.output_folder_var = ctk.StringVar()
        self.mode_var = ctk.StringVar(value="auto")
        self.speed_profile_var = ctk.StringVar(value="2")
        self.format_var = ctk.StringVar(value="3")
        self.quality_var = ctk.StringVar(value="3")
        self.method_var = ctk.StringVar(value="1")
        self.random_delays_var = ctk.BooleanVar(value=True)
        self.batch_size_var = ctk.StringVar(value="5")

        # UI Queues
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()

        # Progress tracking
        self.current_video = 0
        self.total_videos = 0
        self.completed_files = 0
        self.file_progress_widgets: Dict[str, tuple] = {}

        self.setup_ui()
        self.update_log_display()
        self.update_progress_display()

    def setup_ui(self):
        # Main container - Grid layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=2)
        self.root.grid_rowconfigure(0, weight=1)

        # Left Panel - Settings
        left_panel = ctk.CTkFrame(self.root)
        left_panel.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="nsew")

        # Right Panel - Progress & Logs
        right_panel = ctk.CTkFrame(self.root)
        right_panel.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="nsew")

        self.setup_left_panel(left_panel)
        self.setup_right_panel(right_panel)

    def setup_left_panel(self, parent):
        scroll_frame = ctk.CTkScrollableFrame(parent, label_text="⚙️ Settings")
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Title
        title_label = ctk.CTkLabel(
            scroll_frame,
            text="🔗 YouTube Playlist\nDownloader",
            font=ctk.CTkFont(size=20, weight="bold"),
            justify="center"
        )
        title_label.pack(pady=(0, 20))

        # Playlist URL
        url_label = ctk.CTkLabel(scroll_frame, text="Playlist/Video URL(s):", font=ctk.CTkFont(size=13, weight="bold"))
        url_label.pack(anchor="w", padx=5, pady=(10, 5))

        url_entry = ctk.CTkEntry(
            scroll_frame,
            textvariable=self.playlist_url_var,
            placeholder_text="URLs (comma-separated)",
            height=35
        )
        url_entry.pack(fill="x", padx=5, pady=(0, 5))

        # Output Folder
        folder_label = ctk.CTkLabel(scroll_frame, text="Output Folder:", font=ctk.CTkFont(size=13, weight="bold"))
        folder_label.pack(anchor="w", padx=5, pady=(10, 5))

        folder_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        folder_frame.pack(fill="x", padx=5, pady=(0, 10))

        folder_entry = ctk.CTkEntry(
            folder_frame,
            textvariable=self.output_folder_var,
            placeholder_text="Select output folder...",
            height=35
        )
        folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        browse_btn = ctk.CTkButton(
            folder_frame,
            text="📁",
            command=self.browse_folder,
            width=40,
            height=35,
            font=ctk.CTkFont(size=16)
        )
        browse_btn.pack(side="right")

        sep1 = ctk.CTkFrame(scroll_frame, height=2, fg_color="gray30")
        sep1.pack(fill="x", padx=5, pady=15)

        # Mode Selection
        mode_label = ctk.CTkLabel(scroll_frame, text="🧠 Mode Selection:", font=ctk.CTkFont(size=14, weight="bold"))
        mode_label.pack(anchor="w", padx=5, pady=(5, 10))

        auto_radio = ctk.CTkRadioButton(
            scroll_frame,
            text="Auto Select (Recommended)",
            variable=self.mode_var,
            value="auto",
            command=self.toggle_manual_settings,
            font=ctk.CTkFont(size=12)
        )
        auto_radio.pack(anchor="w", padx=10, pady=3)

        manual_radio = ctk.CTkRadioButton(
            scroll_frame,
            text="Manual Settings",
            variable=self.mode_var,
            value="manual",
            command=self.toggle_manual_settings,
            font=ctk.CTkFont(size=12)
        )
        manual_radio.pack(anchor="w", padx=10, pady=3)

        # Manual Settings Frame
        self.manual_settings_frame = ctk.CTkFrame(scroll_frame, fg_color="gray20")

        # Speed Profile
        speed_label = ctk.CTkLabel(self.manual_settings_frame, text="⚡ Speed Profile:", font=ctk.CTkFont(size=12, weight="bold"))
        speed_label.pack(anchor="w", padx=10, pady=(10, 5))

        speed_menu = ctk.CTkOptionMenu(
            self.manual_settings_frame,
            variable=self.speed_profile_var,
            values=["1 - Fast (5 min)", "2 - Medium (8 min)", "3 - Slow (12 min)"],
            font=ctk.CTkFont(size=11)
        )
        speed_menu.pack(fill="x", padx=10, pady=(0, 10))

        # Format Selection
        format_label = ctk.CTkLabel(self.manual_settings_frame, text="📋 Format:", font=ctk.CTkFont(size=12, weight="bold"))
        format_label.pack(anchor="w", padx=10, pady=(5, 5))

        format_menu = ctk.CTkOptionMenu(
            self.manual_settings_frame,
            variable=self.format_var,
            values=["1 - Audio Only", "2 - Video Only", "3 - Video + Audio"],
            command=self.update_quality_options,
            font=ctk.CTkFont(size=11)
        )
        format_menu.pack(fill="x", padx=10, pady=(0, 10))

        # Quality Selection
        quality_label = ctk.CTkLabel(self.manual_settings_frame, text="🎥 Quality:", font=ctk.CTkFont(size=12, weight="bold"))
        quality_label.pack(anchor="w", padx=10, pady=(5, 5))

        self.quality_menu = ctk.CTkOptionMenu(
            self.manual_settings_frame,
            variable=self.quality_var,
            values=["1 - Low", "2 - Medium", "3 - Best"],
            font=ctk.CTkFont(size=11)
        )
        self.quality_menu.pack(fill="x", padx=10, pady=(0, 10))

        # Download Method
        method_label = ctk.CTkLabel(self.manual_settings_frame, text="⬇️ Method:", font=ctk.CTkFont(size=12, weight="bold"))
        method_label.pack(anchor="w", padx=10, pady=(5, 5))

        method_menu = ctk.CTkOptionMenu(
            self.manual_settings_frame,
            variable=self.method_var,
            values=["1 - IDM", "2 - Normal (Python)"],
            font=ctk.CTkFont(size=11)
        )
        method_menu.pack(fill="x", padx=10, pady=(0, 10))

        # Random Delays
        random_check = ctk.CTkCheckBox(
            self.manual_settings_frame,
            text="🎲 Random Delays",
            variable=self.random_delays_var,
            font=ctk.CTkFont(size=11)
        )
        random_check.pack(anchor="w", padx=10, pady=(5, 10))

        # Batch Size
        batch_label = ctk.CTkLabel(self.manual_settings_frame, text="📦 Batch Size:", font=ctk.CTkFont(size=12, weight="bold"))
        batch_label.pack(anchor="w", padx=10, pady=(5, 5))

        batch_entry = ctk.CTkEntry(
            self.manual_settings_frame,
            textvariable=self.batch_size_var,
            placeholder_text="5",
            width=100,
            font=ctk.CTkFont(size=11)
        )
        batch_entry.pack(anchor="w", padx=10, pady=(0, 15))

        sep2 = ctk.CTkFrame(scroll_frame, height=2, fg_color="gray30")
        sep2.pack(fill="x", padx=5, pady=15)

        # Control Buttons
        self.start_btn = ctk.CTkButton(
            scroll_frame,
            text="🚀 Start Download",
            command=self.start_download,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#2B7A0B",
            hover_color="#1F5C08"
        )
        self.start_btn.pack(fill="x", padx=5, pady=(10, 5))

        self.cancel_btn = ctk.CTkButton(
            scroll_frame,
            text="⛔ Cancel",
            command=self.cancel_download,
            height=45,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#8B0000",
            hover_color="#6B0000",
            state="disabled"
        )
        self.cancel_btn.pack(fill="x", padx=5, pady=(5, 10))

    def setup_right_panel(self, parent):
        parent.grid_rowconfigure(0, weight=0)
        parent.grid_rowconfigure(1, weight=2)
        parent.grid_rowconfigure(2, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # Overall Progress
        overall_frame = ctk.CTkFrame(parent)
        overall_frame.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="ew")

        overall_title = ctk.CTkLabel(overall_frame, text="📊 Overall Progress", font=ctk.CTkFont(size=16, weight="bold"))
        overall_title.pack(anchor="w", padx=15, pady=(10, 5))

        self.overall_label = ctk.CTkLabel(
            overall_frame,
            text="Ready to start",
            font=ctk.CTkFont(size=13)
        )
        self.overall_label.pack(anchor="w", padx=15, pady=(0, 5))

        self.overall_progress = ctk.CTkProgressBar(overall_frame, height=22)
        self.overall_progress.pack(fill="x", padx=15, pady=(0, 15))
        self.overall_progress.set(0)

        # Individual Files Progress
        files_frame = ctk.CTkFrame(parent)
        files_frame.grid(row=1, column=0, padx=10, pady=5, sticky="nsew")

        files_title = ctk.CTkLabel(files_frame, text="📁 Files Download Progress", font=ctk.CTkFont(size=16, weight="bold"))
        files_title.pack(anchor="w", padx=15, pady=(10, 5))

        self.files_stats_label = ctk.CTkLabel(
            files_frame,
            text="Total: 0 | Downloading: 0 | Completed: 0",
            font=ctk.CTkFont(size=11),
            text_color="gray60"
        )
        self.files_stats_label.pack(anchor="w", padx=15, pady=(0, 5))

        self.files_scroll = ctk.CTkScrollableFrame(files_frame, fg_color="gray15")
        self.files_scroll.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.files_placeholder = ctk.CTkLabel(
            self.files_scroll,
            text="No downloads in progress",
            font=ctk.CTkFont(size=12),
            text_color="gray50"
        )
        self.files_placeholder.pack(pady=20)

        # Logs
        log_frame = ctk.CTkFrame(parent)
        log_frame.grid(row=2, column=0, padx=10, pady=(5, 10), sticky="nsew")

        log_title = ctk.CTkLabel(log_frame, text="📝 Logs", font=ctk.CTkFont(size=16, weight="bold"))
        log_title.pack(anchor="w", padx=15, pady=(10, 5))

        self.log_text = ctk.CTkTextbox(log_frame, height=120, font=ctk.CTkFont(family="Consolas", size=10))
        self.log_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder_var.set(folder)

    def toggle_manual_settings(self):
        if self.mode_var.get() == "manual":
            self.manual_settings_frame.pack(fill="x", padx=5, pady=(10, 0), before=self.start_btn.master.children[list(self.start_btn.master.children.keys())[-3]])
        else:
            self.manual_settings_frame.pack_forget()

    def update_quality_options(self, choice):
        format_choice = self.format_var.get()[0]
        if format_choice == "1":
            self.quality_menu.configure(values=["1 - Low (≤64kbps)", "2 - Medium (96-128kbps)", "3 - Best"])
        else:
            self.quality_menu.configure(values=["1 - Low (≤360p)", "2 - Medium (480p-720p)", "3 - Best"])

    def log(self, message: str):
        self.log_queue.put(message)

    def add_file_progress(self, file_name: str, task_id: str):
        if hasattr(self, 'files_placeholder') and self.files_placeholder.winfo_exists():
            self.files_placeholder.destroy()

        file_frame = ctk.CTkFrame(self.files_scroll, fg_color="gray25")
        file_frame.pack(fill="x", padx=5, pady=3)

        display_name = file_name if len(file_name) <= 50 else file_name[:47] + "..."
        name_label = ctk.CTkLabel(
            file_frame,
            text=f"📄 {display_name}",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w"
        )
        name_label.pack(anchor="w", padx=10, pady=(8, 2))

        progress_bar = ctk.CTkProgressBar(file_frame, height=16)
        progress_bar.pack(fill="x", padx=10, pady=(0, 2))
        progress_bar.set(0)

        status_label = ctk.CTkLabel(
            file_frame,
            text="Starting...",
            font=ctk.CTkFont(size=10),
            text_color="gray60"
        )
        status_label.pack(anchor="w", padx=10, pady=(0, 8))

        self.file_progress_widgets[task_id] = (file_frame, name_label, progress_bar, status_label)

    def update_progress_safely(self, task_id: str, url: str, percent: Optional[float], status_msg: str):
        self.progress_queue.put({
            'task_id': task_id,
            'url': url,
            'percent': percent,
            'status': status_msg
        })

    def toggle_ui_state(self, enabled: bool):
        self.root.after(0, lambda: self._toggle_ui_state_sync(enabled))

    def _toggle_ui_state_sync(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.start_btn.configure(state=state)
        self.cancel_btn.configure(state="disabled" if enabled else "normal")

    def validate_inputs(self) -> bool:
        if not self.playlist_url_var.get().strip():
            messagebox.showerror("Error", "Please enter a playlist URL")
            return False
        if not self.output_folder_var.get().strip():
            messagebox.showerror("Error", "Please select an output folder")
            return False
        return True

    def start_download(self):
        if not self.validate_inputs():
            return

        self.toggle_ui_state(False)
        self.log_text.delete("1.0", "end")

        for task_id in list(self.file_progress_widgets.keys()):
            self.file_progress_widgets[task_id][0].destroy()
        self.file_progress_widgets.clear()

        playlist_urls_input = self.playlist_url_var.get().strip()
        urls = [url.strip() for url in playlist_urls_input.split(',') if url.strip()]
        
        output_base = os.path.abspath(self.output_folder_var.get().strip())
        os.makedirs(output_base, exist_ok=True)
        cookies_file = os.path.join(output_base, "yt_cookies.txt")

        batch_size = 5
        try:
            batch_size = int(self.batch_size_var.get().strip())
            if batch_size < 1:
                batch_size = 5
        except:
            pass

        # Parse config for controller
        speed_map = {"1": (5*60, 2), "2": (8*60, 3), "3": (12*60, 5)}
        speed_choice = self.speed_profile_var.get()[0]
        wait_time, short_delay = speed_map.get(speed_choice, (8*60, 3))

        config = DownloadConfig(
            format_choice=self.format_var.get()[0],
            quality_choice=self.quality_var.get()[0],
            download_mode="idm" if self.method_var.get()[0] == "1" else "python",
            wait_time=wait_time,
            short_delay=short_delay,
            use_random=self.random_delays_var.get(),
            max_concurrent=batch_size,
            output_dir=output_base,
            cookies_file=cookies_file
        )
        
        self.log(f"[{now()}] 🚀 Starting download orchestration...")
        
        import threading
        def _extract_and_start():
            from extractor import extract_playlist_info
            all_video_urls = []
            for url in urls:
                try:
                    self.log(f"[{now()}] 📥 Extracting URLs from: {url}")
                    _, extracted_urls = extract_playlist_info(url)
                    all_video_urls.extend(extracted_urls)
                except Exception as e:
                    self.log(f"[{now()}] ❌ Failed to extract {url}: {e}")
            
            if not all_video_urls:
                self.log(f"[{now()}] ❌ No valid video URLs found.")
                self.toggle_ui_state(True)
                return
                
            self.total_videos = len(all_video_urls)
            self.current_video = 0
            self.root.after(0, lambda: self.controller.start_downloads(config, all_video_urls))
            
        threading.Thread(target=_extract_and_start, daemon=True).start()

    def cancel_download(self):
        self.log(f"[{now()}] ⛔ Canceling... In-flight downloads will stop shortly...")
        self.cancel_btn.configure(state="disabled")
        self.controller.cancel_all()

    def update_log_display(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_text.insert("end", message + "\n")
                self.log_text.see("end")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.update_log_display)

    def update_progress_display(self):
        try:
            while True:
                progress_data = self.progress_queue.get_nowait()
                task_id = progress_data['task_id']
                url = progress_data['url']
                percent = progress_data['percent']
                status = progress_data['status']

                if task_id not in self.file_progress_widgets:
                    self.add_file_progress(url, task_id)

                frame, name_label, progress_bar, status_label = self.file_progress_widgets[task_id]
                
                # Check previous status to avoid multiple increments
                prev_status = status_label.cget("text")
                status_label.configure(text=status)
                
                if percent is not None:
                    progress_bar.set(percent / 100.0)

                terminal_statuses = ["Complete", "Failed during download", "Canceled", "Failed", "Failed:"]
                is_terminal = any(status.startswith(ts) for ts in terminal_statuses)
                was_terminal = any(prev_status.startswith(ts) for ts in terminal_statuses)

                if is_terminal and not was_terminal:
                    self.current_video += 1
                    if self.total_videos > 0:
                        overall_percent = self.current_video / self.total_videos
                        self.overall_progress.set(overall_percent)
                        self.overall_label.configure(text=f"Completed: {self.current_video} / {self.total_videos} videos ({overall_percent*100:.1f}%)")

        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.update_progress_display)

if __name__ == "__main__":
    from controller import DownloaderController
    root = ctk.CTk()
    view = DownloaderView(root, None)
    controller = DownloaderController(view)
    view.controller = controller
    root.mainloop()
