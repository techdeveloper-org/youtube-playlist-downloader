import pytest
import threading
import time
from unittest.mock import MagicMock
from controller import DownloaderController
from model import DownloadConfig

class MockView:
    def __init__(self):
        self.updates = []
        self.toggled_state = None

    def toggle_ui_state(self, enabled):
        self.toggled_state = enabled

    def toggle_ui_state_safely(self, enabled):
        self.toggled_state = enabled

    def update_progress_safely(self, task_id, url, percent, status_msg):
        self.updates.append((task_id, url, percent, status_msg))


def test_controller_initialization():
    view = MockView()
    controller = DownloaderController(view)
    assert not controller._executor_active
    assert controller._active_tasks_count == 0

def test_controller_empty_urls():
    view = MockView()
    controller = DownloaderController(view)
    config = DownloadConfig(
        format_choice="3",
        quality_choice="3",
        download_mode="python",
        wait_time=0,
        short_delay=0,
        use_random=False,
        max_concurrent=5,
        output_dir="/tmp",
        cookies_file="/tmp/cookies.txt"
    )
    controller.start_downloads(config, [])
    assert not controller._executor_active
    assert controller._current_run_id is None

def test_controller_cancel_all():
    view = MockView()
    controller = DownloaderController(view)
    config = DownloadConfig(
        format_choice="3",
        quality_choice="3",
        download_mode="python",
        wait_time=0,
        short_delay=0,
        use_random=False,
        max_concurrent=5,
        output_dir="/tmp",
        cookies_file="/tmp/cookies.txt"
    )
    controller.start_downloads(config, [("Test Title", "http://test")])
    
    # Give orchestrator thread a moment to spawn
    time.sleep(0.1)
    
    controller.cancel_all()
    assert controller.cancel_event.is_set()
    assert not controller._executor_active
    assert view.toggled_state is True
