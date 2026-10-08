import threading
import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class DownloadConfig:
    """
    Holds the application configuration settings for downloading videos.
    """
    format_choice: str
    quality_choice: str
    output_dir: str
    cookies_file: Optional[str]
    download_mode: str
    max_concurrent: int = 3
    short_delay: int = 2
    wait_time: int = 300
    use_random: bool = False

class PlaylistState:
    """
    Manages the state of the download playlist, including tasks, URLs, statuses, and progress.
    Ensures thread-safe operations on state variables.
    """
    def __init__(self) -> None:
        """
        Initializes the PlaylistState with empty collections and a reentrant lock.
        """
        self.tasks: List[str] = []
        self.urls: Dict[str, str] = {}
        self.titles: Dict[str, str] = {}
        self.status: Dict[str, str] = {}
        self.progress: Dict[str, float] = {}
        self.lock = threading.Lock()

    def add_task(self, url: str, title: str = "Unknown") -> str:
        """
        Adds a new URL to the playlist and returns a uniquely generated task ID.

        Args:
            url (str): The target URL to download.
            title (str): The video title.

        Returns:
            str: A unique UUID string representing the task.
        """
        task_id = str(uuid.uuid4())
        with self.lock:
            self.tasks.append(task_id)
            self.urls[task_id] = url
            self.titles[task_id] = title
            self.status[task_id] = "pending"
            self.progress[task_id] = 0.0
        return task_id

    def set_status(self, task_id: str, status: str) -> None:
        """
        Updates the status of a specific task.

        Args:
            task_id (str): The unique task identifier.
            status (str): The new status string (e.g., 'downloading', 'completed').
        """
        with self.lock:
            if task_id in self.status:
                self.status[task_id] = status

    def get_status(self, task_id: str) -> Optional[str]:
        with self.lock:
            return self.status.get(task_id)

    def get_tasks_with_status(self, target_statuses: List[str]) -> List[str]:
        """
        Retrieves a list of task IDs that match any of the provided target statuses.

        Args:
            target_statuses (List[str]): A list of status strings to filter by.

        Returns:
            List[str]: A list of task IDs.
        """
        with self.lock:
            return [tid for tid, stat in self.status.items() if stat in target_statuses]

    def reset(self) -> None:
        """
        Clears all tasks, URLs, statuses, and progress from the state.
        """
        with self.lock:
            self.tasks.clear()
            self.urls.clear()
            self.titles.clear()
            self.status.clear()
            self.progress.clear()
