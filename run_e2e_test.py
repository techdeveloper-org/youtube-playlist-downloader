import threading
import time
from controller import DownloaderController
from model import DownloadConfig

class MockView:
    def __init__(self):
        self.controller = None
    def add_to_playlist(self, url, title):
        print(f"Added to playlist: {title} ({url})")
    def update_task_progress(self, task_id, percent, status):
        print(f"[{task_id}] {percent:.1f}% - {status}")
    def update_progress_safely(self, task_id, title, percent, status):
        pct_str = f"{percent:.1f}%" if percent is not None else "---%"
        print(f"[{task_id}] {title} {pct_str} - {status}")
    def log(self, msg):
        print(f"LOG: {msg}")
    def log_safely(self, msg):
        print(f"LOG: {msg}")
    def toggle_ui_state(self, is_active):
        print(f"UI STATE: {'ACTIVE' if is_active else 'IDLE'}")
    def toggle_ui_state_safely(self, is_active):
        print(f"UI STATE: {'ACTIVE' if is_active else 'IDLE'}")
    def show_error(self, title, msg):
        print(f"ERROR: {title} - {msg}")
    def show_error_safely(self, title, msg):
        print(f"ERROR: {title} - {msg}")
    def update_stats(self, success, failed, remaining):
        print(f"STATS: {success} Success, {failed} Failed, {remaining} Remaining")
    def update_stats_safely(self, success, failed, remaining):
        print(f"STATS: {success} Success, {failed} Failed, {remaining} Remaining")

def run_test():
    view = MockView()
    controller = DownloaderController(view)
    view.controller = controller
    
    # 5 second test video
    urls = [("Test Video", "https://www.youtube.com/watch?v=jNQXAC9IVRw")]
    
    config = DownloadConfig(
        format_choice="3",
        quality_choice="1",
        output_dir="./test_downloads",
        cookies_file="",
        download_mode="Sequential"
    )
    config.downloader_choice = "1"
    
    import os
    if not os.path.exists(config.output_dir):
        os.makedirs(config.output_dir)
        
    print("Starting downloads...")
    # Wrap in root.after mock since controller uses it
    # We can just mock view.root.after in controller or handle it.
    controller.start_downloads(config, urls)
    
    import time
    time.sleep(1)
    
    # Wait until it becomes active first (up to 5s)
    for _ in range(50):
        if controller._executor_active:
            break
        time.sleep(0.1)
        
    print("Executor is now active. Waiting for it to finish...")
    # Wait for completion
    while controller._executor_active:
        time.sleep(1)
        
    print("Test finished! Waiting for daemon threads if any...")
    time.sleep(3)

if __name__ == "__main__":
    run_test()
