```mermaid
gantt
    title Conceptual Downloader Timing
    dateFormat  s
    axisFormat %S
    
    section Setup
    GUI Validation & yt-dlp hook : 0, 2s
    
    section Orchestration
    _orchestrator_thread init : 2, 3s
    ThreadPool Allocation : 3, 4s
    
    section Worker 1 (Video)
    extract_direct_download_info : 4, 8s
    select_video_format : 8, 9s
    PythonDownloader.download : 9, 20s
    
    section Worker 2 (Audio)
    extract_direct_download_info : 5, 9s
    select_audio_format : 9, 10s
    IDMDownloader.download : 10, 16s
```

