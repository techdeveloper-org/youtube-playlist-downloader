import threading
import uuid
import time
from typing import List, Callable, Optional
from concurrent.futures import ThreadPoolExecutor

from model import DownloadConfig, PlaylistState
from downloaders import DownloaderStrategy, PythonDownloader, IDMDownloader
from extractor import extract_direct_download_info
from utils import get_random_delay


class DownloaderController:
    """
    Orchestrates the background execution of downloads, strategy injection, and UI updates.
    """
    def __init__(self, view):
        self.view = view
        self.model = PlaylistState()
        self.cancel_event = threading.Event()
        self.executor = None
        self._executor_active = False
        self._current_run_id = None
        self._active_tasks_count = 0
        self._controller_lock = threading.Lock()

    def _sleep_with_cancel(self, seconds: float, cancel_event: threading.Event) -> None:
        """Helper to sleep while remaining responsive to cancellation."""
        end = time.time() + seconds
        while time.time() < end and not cancel_event.is_set():
            time.sleep(0.2)

    def start_downloads(self, config: DownloadConfig, urls: List[str]) -> None:
        if config.max_concurrent <= 0:
            raise ValueError("max_concurrent must be > 0")
            
        with self._controller_lock:
            # 1. Cancel old run and shutdown executor
            if self._executor_active and self.executor is not None:
                self.cancel_event.set()
                self.executor.shutdown(wait=False, cancel_futures=True)
                
            # 2. Handle empty URL list cleanly
            if not urls:
                self._executor_active = False
                self._current_run_id = None
                self.model.reset()
                return
                
            self.model.reset()
            self.cancel_event = threading.Event()
            self.executor = ThreadPoolExecutor(max_workers=config.max_concurrent)
            self._executor_active = True
            self._current_run_id = str(uuid.uuid4())
            self._active_tasks_count = len(urls)
            
            # Start the orchestrator thread
            threading.Thread(
                target=self._orchestrator_thread,
                args=(config, urls, self.cancel_event, self._current_run_id),
                daemon=True
            ).start()

    def cancel_all(self) -> None:
        with self._controller_lock:
            self.cancel_event.set()
            if self.executor is not None:
                self.executor.shutdown(wait=False, cancel_futures=True)
            self._executor_active = False
            self._current_run_id = None
            
        # Update pending/downloading tasks to canceled
        active_tasks = self.model.get_tasks_with_status(["pending", "downloading"])
        for task_id in active_tasks:
            self.model.set_status(task_id, "canceled")
            self._notify_view(task_id, None, "Canceled")
        
        self.view.toggle_ui_state(True)

    def _orchestrator_thread(self, config: DownloadConfig, urls: List[str], cancel_event: threading.Event, run_id: str) -> None:
        batch_size = 5
        for idx, url in enumerate(urls):
            if cancel_event.is_set() or run_id != self._current_run_id:
                break
                
            task_id = self.model.add_task(url)
            self._notify_view(task_id, 0.0, "Queued...")
            
            self.executor.submit(self._worker_task, task_id, url, config, cancel_event, run_id)
            
            # Short delay between submissions
            if idx < len(urls) - 1:
                short_delay = config.short_delay
                if config.use_random:
                    import random
                    short_delay = random.uniform(short_delay * 0.8, short_delay * 1.2)
                self._sleep_with_cancel(short_delay, cancel_event)

            # Wait time between batches
            if (idx + 1) % batch_size == 0 and idx < len(urls) - 1:
                wait_time = config.wait_time
                if config.use_random:
                    wait_time = get_random_delay(wait_time // 60) * 60 # get_random_delay returns seconds
                self._sleep_with_cancel(wait_time, cancel_event)

    def _notify_view(self, task_id: str, percent: Optional[float], status_msg: str) -> None:
        """Safely dispatches UI updates to the main thread."""
        # CustomTkinter after() is thread-safe
        url = self.model.urls.get(task_id, "Unknown URL")
        self.view.update_progress_safely(task_id, url, percent, status_msg)

    def _worker_task(self, task_id: str, url: str, config: DownloadConfig, cancel_event: threading.Event, run_id: str) -> None:
        if run_id != self._current_run_id:
            return
            
        if cancel_event.is_set():
            self.model.set_status(task_id, "canceled")
            self._notify_view(task_id, None, "Canceled")
            self._decrement_task(run_id)
            return
            
        self.model.set_status(task_id, "downloading")
        self._notify_view(task_id, 0.0, "Extracting info...")
        
        try:
            info, error = extract_direct_download_info(url, config.format_choice, config.quality_choice, config.cookies_file)
            if error or not info:
                self.model.set_status(task_id, "failed")
                self._notify_view(task_id, None, f"Failed: {error}")
                return
                
            if cancel_event.is_set():
                self.model.set_status(task_id, "canceled")
                self._notify_view(task_id, None, "Canceled")
                return

            # Select strategy
            strategy = IDMDownloader() if config.download_mode == "idm" else PythonDownloader()
            
            # Progress callback adapter
            def progress_adapter(t_id: str, pct: float, msg: str):
                if not cancel_event.is_set():
                    self._notify_view(t_id, pct, msg)
            
            success = strategy.download(info, config, task_id, progress_adapter, cancel_event)
            
            if cancel_event.is_set():
                self.model.set_status(task_id, "canceled")
                self._notify_view(task_id, None, "Canceled")
            else:
                self.model.set_status(task_id, "completed" if success else "failed")
                self._notify_view(task_id, 100.0 if success else None, "Complete" if success else "Failed during download")
                
        except Exception as e:
            self.model.set_status(task_id, "failed")
            self._notify_view(task_id, None, f"Error: {str(e)}")
        finally:
            self._decrement_task(run_id)
            
    def _decrement_task(self, run_id: str) -> None:
        with self._controller_lock:
            if run_id != self._current_run_id:
                return
            self._active_tasks_count -= 1
            if self._active_tasks_count <= 0:
                self._executor_active = False
                if self.executor is not None:
                    self.executor.shutdown(wait=False)
                # Re-enable UI
                self.view.toggle_ui_state(True)
