```mermaid
flowchart TB
    subgraph UI Layer
        DownloaderView[gui.py]
    end
    
    subgraph Controller Layer
        DownloaderController[controller.py]
        PlaylistState[model.py]
    end
    
    subgraph Core Processing
        Extractor[extractor.py]
        FormatSelector[formats.py]
    end
    
    subgraph Downloaders
        DownloaderStrategy[downloaders.py]
        PythonDownloader[PythonDownloader]
        IDMDownloader[IDMDownloader]
    end
    
    subgraph Utils
        FilesIO[files_io.py]
        SpeedTest[speedtest_utils.py]
    end
    
    DownloaderView <--> DownloaderController
    DownloaderController --> PlaylistState
    DownloaderController --> Extractor
    DownloaderController --> FormatSelector
    DownloaderController --> DownloaderStrategy
    DownloaderStrategy <|-- PythonDownloader
    DownloaderStrategy <|-- IDMDownloader
    DownloaderController --> FilesIO
    DownloaderController --> SpeedTest
```

