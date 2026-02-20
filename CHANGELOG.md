# Changelog

## v1.2

### New
- Desktop GUI app built with CustomTkinter, replacing the terminal interface
- Wizard-style setup flow — each step unlocks only after the previous is complete
- Token verification checks your API key and loads your Vimeo folders before continuing
- Folder browser for choosing where to save downloads
- Per-worker progress bars showing filename, size, and download speed for each of the 3 concurrent downloads
- Overall progress bar with total bandwidth usage
- Stop button with confirmation dialog — cancels all active downloads and removes any partial files

### Improved
- API token is always entered at runtime, never stored in the script
- Download folder is organised automatically into a `vimeo_downloads` subfolder
- App instructions include a built-in guide on how to get a Vimeo API token
- Disclaimer added reminding users to only download their own content

### Project
- Restructured into `src/` with separate files for UI and download logic
- PyInstaller build configs added for macOS (`.app`) and Windows (`.exe`)
- `.gitignore` cleaned up to only cover what's relevant to this project

---

## v1.1 (CLI)

- Removed hardcoded API key — token is now entered at runtime
- Guided terminal flow: token → download folder → Vimeo folder → quality → start
