# Vimeo Downloader

![Build macOS](https://github.com/rhodrihughes/VimeoDownloader/actions/workflows/build-macos.yml/badge.svg)
![Latest Release](https://img.shields.io/github/v/release/rhodrihughes/VimeoDownloader)
![macOS](https://img.shields.io/badge/macOS-13%2B-blue?logo=apple)
![Python](https://img.shields.io/badge/python-3.13-blue?logo=python)

Downloads source video files from a Vimeo account via the Vimeo API.

## Download

[⬇ Download latest release](https://github.com/rhodrihughes/VimeoDownloader/releases/latest)

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
