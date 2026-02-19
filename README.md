# Vimeo Downloader

Downloads source video files from a Vimeo account via the Vimeo API.

## Setup

```bash
pip install -r requirements.txt
```

## Run (development)

```bash
python src/main.py
```

## Build

### macOS (.app)
```bash
pyinstaller build/mac.spec
```
Output: `dist/VimeoDownloader.app`

### Windows (.exe)
```bash
pyinstaller build/windows.spec
```
Output: `dist/VimeoDownloader.exe`

## Icons
Place `icon.icns` (macOS) and `icon.ico` (Windows) in the `assets/` folder before building.
