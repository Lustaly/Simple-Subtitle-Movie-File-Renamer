## Core Function
This script ensures uniform naming between media files and their corresponding subtitles for seamless playback integration.

## Operational Logic
1. **Metadata Stripping:** Eliminates structural noise such as resolution metrics, codec types, and release group tags (e.g., 1080p, x264, HDR, WEB-DL).
2. **Title Extraction:** Utilizes regex patterns to isolate the core title, release year, or Season/Episode identifiers.
3. **File Synchronization:** Renames both the video and subtitle files to the exact matched standard, ensuring media players detect and load subtitles automatically.
