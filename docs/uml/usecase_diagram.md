```mermaid
flowchart LR
    User([End User])
    
    User --> (Paste Playlist URL)
    User --> (Select Video/Audio Quality)
    User --> (Start Download)
    User --> (Monitor Progress)
    User --> (Cancel Download)
    
    (Start Download) ..> (Validate URL) : <<includes>>
    (Start Download) ..> (Extract Video Metadata) : <<includes>>
    (Cancel Download) ..> (Abort Active Threads) : <<includes>>
    
    (Monitor Progress) --- Sys([System])
    (Validate URL) --- Sys
```