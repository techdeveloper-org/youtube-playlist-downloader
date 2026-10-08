```mermaid
classDiagram
    class DownloaderSystem {
        <<System>>
    }
    class UI {
        <<Component>>
        DownloaderView
    }
    class CoreLogic {
        <<Component>>
        DownloaderController
        PlaylistState
        DownloaderStrategy
    }
    class ExternalIntegrations {
        <<Component>>
        yt-dlp (Extractor)
        IDM
    }
    DownloaderSystem *-- UI
    DownloaderSystem *-- CoreLogic
    DownloaderSystem *-- ExternalIntegrations
```

