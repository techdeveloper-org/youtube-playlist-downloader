```mermaid
classDiagram
    namespace GUI {
        class gui
    }
    namespace Core {
        class main
        class controller
        class model
    }
    namespace Processing {
        class extractor
        class formats
        class downloaders
    }
    namespace Utilities {
        class files_io
        class paths
        class speedtest_utils
        class utils
    }
    GUI ..> Core : Uses
    Core ..> Processing : Orchestrates
    Processing ..> Utilities : Relies on
```