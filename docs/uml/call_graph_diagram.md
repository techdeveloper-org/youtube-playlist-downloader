```mermaid
flowchart LR
    gui.start_download --> extractor.extract_playlist_info
    gui.start_download --> controller.start_downloads
    controller.start_downloads --> controller._orchestrator_thread
    controller._orchestrator_thread --> controller._worker_task
    controller._worker_task --> extractor.extract_direct_download_info
    controller._worker_task --> formats.select_combined_format
    controller._worker_task --> downloaders.PythonDownloader.download
    downloaders.PythonDownloader.download --> controller._notify_view
    controller._notify_view --> gui.update_progress_safely
```