import pytest
from model import DownloadConfig, PlaylistState

def test_download_config_defaults():
    config = DownloadConfig(
        format_choice="3",
        quality_choice="3",
        download_mode="python",
        wait_time=300,
        short_delay=3,
        use_random=False,
        max_concurrent=5,
        output_dir="/tmp",
        cookies_file="/tmp/cookies.txt"
    )
    assert config.max_concurrent == 5

def test_playlist_state_tracking():
    state = PlaylistState()
    task_id1 = state.add_task("http://test1")
    task_id2 = state.add_task("http://test2")
    
    assert len(state.urls) == 2
    assert state.get_status(task_id1) == "pending"
    
    state.set_status(task_id1, "downloading")
    assert state.get_status(task_id1) == "downloading"
    
    active_tasks = state.get_tasks_with_status(["pending", "downloading"])
    assert len(active_tasks) == 2
    
    state.reset()
    assert len(state.urls) == 0
