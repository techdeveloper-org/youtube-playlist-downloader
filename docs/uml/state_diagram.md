```mermaid
stateDiagram-v2
    [*] --> Pending : add_task()
    Pending --> Extracting : _worker_task()
    Extracting --> Failed : Extraction Error
    Extracting --> Downloading : Formats Selected
    Downloading --> Paused : (Not fully supported)
    Downloading --> Failed : Network/Write Error
    Failed --> Extracting : Retry (future scope)
    Downloading --> Cancelled : cancel_all()
    Downloading --> Completed : File Saved
    Completed --> [*]
    Cancelled --> [*]
```