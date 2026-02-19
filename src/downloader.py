#!/usr/bin/env python3
"""
Core Vimeo download logic - no UI dependencies.
"""

import os
import requests
import csv
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm


class VimeoDownloader:
    def __init__(self, access_token, download_dir=None, testing_mode=False, max_pages=None,
                 max_videos=None, quality_preference="source", enable_multithreading=False,
                 max_workers=3, force_source=False, log_callback=None):
        self.access_token = access_token
        self.base_url = "https://api.vimeo.com"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.vimeo.*+json;version=3.4"
        }

        self.testing_mode = testing_mode
        self.max_pages = max_pages
        self.max_videos = max_videos
        self.quality_preference = quality_preference
        self.force_source = force_source
        self.enable_multithreading = enable_multithreading
        self.max_workers = max_workers
        self.csv_lock = threading.Lock()

        # Optional callback for GUI log output: log_callback(message: str)
        self.log_callback = log_callback

        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = Path("vimeo_downloads")

        self.download_dir.mkdir(exist_ok=True, parents=True)
        self._log(f"✓ Download directory: {self.download_dir.absolute()}")

        self.csv_path = self.download_dir / "download_log.csv"
        self.retry_csv_path = self.download_dir / "retry_later.csv"
        self.init_csv_log()
        self.init_retry_csv()

    def _log(self, message):
        """Send log message to callback if set, otherwise print."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def init_csv_log(self):
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Video ID', 'Title', 'Folder Path', 'Upload Date',
                    'Privacy', 'Quality Downloaded', 'Resolution',
                    'File Size (MB)', 'Status', 'Error Message', 'Download Date'
                ])

    def init_retry_csv(self):
        if not self.retry_csv_path.exists():
            with open(self.retry_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Video ID', 'Title', 'Folder Path', 'Upload Date',
                    'Privacy', 'Video URL', 'Reason', 'Flagged Date'
                ])

    def log_to_csv(self, video_data):
        with self.csv_lock:
            with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    video_data.get('video_id', ''),
                    video_data.get('title', ''),
                    video_data.get('folder_path', ''),
                    video_data.get('upload_date', ''),
                    video_data.get('privacy', ''),
                    video_data.get('quality', ''),
                    video_data.get('resolution', ''),
                    video_data.get('file_size_mb', ''),
                    video_data.get('status', ''),
                    video_data.get('error_message', ''),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ])

    def log_to_retry_csv(self, video_data):
        with self.csv_lock:
            with open(self.retry_csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    video_data.get('video_id', ''),
                    video_data.get('title', ''),
                    video_data.get('folder_path', ''),
                    video_data.get('upload_date', ''),
                    video_data.get('privacy', ''),
                    video_data.get('video_url', ''),
                    video_data.get('reason', ''),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ])

    def get_retry_videos(self):
        if not self.retry_csv_path.exists():
            self._log("❌ No retry_later.csv file found")
            return []

        self._log("📋 Reading videos from retry_later.csv...")
        retry_video_ids = []
        with open(self.retry_csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                video_id = row.get('Video ID')
                if video_id:
                    retry_video_ids.append(video_id)

        if not retry_video_ids:
            self._log("❌ No videos found in retry_later.csv")
            return []

        self._log(f"✓ Found {len(retry_video_ids)} videos to retry")
        videos = []
        for video_id in retry_video_ids:
            try:
                url = f"{self.base_url}/videos/{video_id}"
                params = {"fields": "uri,name,description,privacy,download,files,created_time,parent_folder"}
                response = requests.get(url, headers=self.headers, params=params)
                if response.status_code == 200:
                    videos.append(response.json())
                else:
                    self._log(f"⚠️  Could not fetch video {video_id}: {response.status_code}")
            except Exception as e:
                self._log(f"⚠️  Error fetching video {video_id}: {str(e)}")

        self._log(f"✓ Fetched {len(videos)} videos")
        return videos

    def remove_from_retry_csv(self, video_id):
        with self.csv_lock:
            if not self.retry_csv_path.exists():
                return
            rows_to_keep = []
            with open(self.retry_csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row.get('Video ID') != video_id:
                        rows_to_keep.append(row)
            with open(self.retry_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows_to_keep)

    def get_user_folders(self):
        folders = []
        page = 1
        while True:
            url = f"{self.base_url}/me/projects"
            params = {"page": page, "per_page": 100, "fields": "uri,name"}
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                self._log(f"❌ Error fetching folders: {response.status_code}")
                break
            data = response.json()
            folders.extend(data.get("data", []))
            if not data.get("paging", {}).get("next"):
                break
            page += 1
        return folders

    def get_videos_from_folder(self, folder_id):
        videos = []
        page = 1
        while True:
            if self.testing_mode and self.max_pages and page > self.max_pages:
                break
            url = f"{self.base_url}/me/projects/{folder_id}/videos"
            params = {
                "page": page, "per_page": 100,
                "fields": "uri,name,description,privacy,download,files,created_time,parent_folder"
            }
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                break
            data = response.json()
            videos.extend(data.get("data", []))
            if not data.get("paging", {}).get("next"):
                break
            page += 1
        return videos

    def get_user_videos(self):
        videos = []
        page = 1
        self._log("📡 Fetching videos from Vimeo API...")
        while True:
            if self.testing_mode and self.max_pages and page > self.max_pages:
                break
            url = f"{self.base_url}/me/videos"
            params = {
                "page": page, "per_page": 100,
                "fields": "uri,name,description,privacy,download,files,created_time,parent_folder"
            }
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                self._log(f"❌ Error fetching videos: {response.status_code}")
                break
            data = response.json()
            videos.extend(data.get("data", []))
            if not data.get("paging", {}).get("next"):
                break
            page += 1
        self._log(f"✓ Found {len(videos)} videos")
        return videos

    def get_folder_path(self, video):
        folder_path = []
        parent_folder = video.get("parent_folder")
        if parent_folder and parent_folder.get("uri"):
            folder_id = parent_folder["uri"].split("/")[-1]
            try:
                url = f"{self.base_url}/me/projects/{folder_id}"
                response = requests.get(url, headers=self.headers)
                if response.status_code == 200:
                    folder_data = response.json()
                    folder_name = folder_data.get("name", f"folder_{folder_id}")
                    folder_path.append(self.sanitize_filename(folder_name))
            except Exception:
                pass
        return "/".join(folder_path) if folder_path else ""

    def get_download_link_by_quality(self, video):
        video_id = video["uri"].split("/")[-1]
        download_links = video.get("download", [])

        if not download_links:
            url = f"{self.base_url}/videos/{video_id}"
            response = requests.get(url, headers=self.headers, params={"fields": "download,files"})
            if response.status_code == 200:
                download_links = response.json().get("download", [])

        if download_links:
            download_links.sort(key=lambda x: x.get("height", 0), reverse=True)

            if self.force_source:
                source_link = next((l for l in download_links if l.get("quality") == "source"), None)
                if source_link:
                    return source_link
                return {"error": "no_source", "available_qualities": [l.get("quality") for l in download_links]}

            quality_heights = {"1080p": 1080, "720p": 720, "540p": 540}
            if self.quality_preference in quality_heights:
                target = quality_heights[self.quality_preference]
                match = next((l for l in download_links if l.get("height") == target), None)
                return match or download_links[0]

            return download_links[0]

        files = [f for f in video.get("files", []) if f.get("quality") != "hls"]
        if files:
            files.sort(key=lambda x: x.get("height", 0), reverse=True)
            return files[0]

        return None

    def sanitize_filename(self, filename):
        for char in '<>:"/\\|?*':
            filename = filename.replace(char, "_")
        return filename

    def download_video(self, video, index, total, progress_callback=None):
        """Download a single video. progress_callback(bytes_downloaded, total_bytes)."""
        video_name = video.get("name", "Untitled")
        video_id = video["uri"].split("/")[-1]
        privacy = video.get('privacy', {}).get('view', 'unknown')
        upload_date = video.get('created_time', 'Unknown')

        if upload_date != 'Unknown':
            try:
                upload_date = datetime.fromisoformat(upload_date.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            except Exception:
                pass

        folder_path = self.get_folder_path(video)
        self._log(f"[{index}/{total}] {video_name}")

        log_data = {
            'video_id': video_id, 'title': video_name, 'folder_path': folder_path,
            'upload_date': upload_date, 'privacy': privacy,
            'quality': '', 'resolution': '', 'file_size_mb': '',
            'status': 'Failed', 'error_message': ''
        }

        download_info = self.get_download_link_by_quality(video)

        if isinstance(download_info, dict) and download_info.get("error") == "no_source":
            error_msg = f"Source not available. Qualities: {', '.join(download_info.get('available_qualities', []))}"
            self._log(f"  ⚠️  {error_msg} — flagged for retry")
            self.log_to_retry_csv({
                'video_id': video_id, 'title': video_name, 'folder_path': folder_path,
                'upload_date': upload_date, 'privacy': privacy,
                'video_url': f"https://vimeo.com/{video_id}", 'reason': error_msg
            })
            log_data.update({'error_message': error_msg, 'status': 'Retry Later (No Source)'})
            self.log_to_csv(log_data)
            return 'retry'

        if not download_info:
            error_msg = "No download link available"
            self._log(f"  ⚠️  {error_msg}")
            log_data['error_message'] = error_msg
            self.log_to_csv(log_data)
            return False

        download_url = download_info.get("link")
        quality = download_info.get("quality", "unknown")
        height = download_info.get("height", "unknown")
        size_mb = download_info.get("size", 0) / (1024 * 1024)

        log_data.update({'quality': quality, 'resolution': f"{height}p", 'file_size_mb': f"{size_mb:.2f}"})

        if not download_url:
            log_data['error_message'] = "No download URL"
            self.log_to_csv(log_data)
            return False

        self._log(f"  Quality: {quality} ({height}p) | Size: {size_mb:.1f} MB")

        if folder_path:
            video_dir = self.download_dir / folder_path
            video_dir.mkdir(exist_ok=True, parents=True)
        else:
            video_dir = self.download_dir

        safe_name = self.sanitize_filename(video_name)
        extension = download_info.get("type", "video/mp4").split("/")[-1]
        filepath = video_dir / f"{video_id}_{safe_name}.{extension}"

        if filepath.exists():
            self._log(f"  ⏭️  Already downloaded, skipping")
            log_data['status'] = 'Skipped (Already exists)'
            self.log_to_csv(log_data)
            return True

        try:
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0

            with open(filepath, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total_size)

            self._log(f"  ✅ Saved: {filepath.name}")
            log_data['status'] = 'Success'
            self.log_to_csv(log_data)
            self.remove_from_retry_csv(video_id)
            return True

        except Exception as e:
            error_msg = str(e)
            self._log(f"  ❌ Error: {error_msg}")
            log_data['error_message'] = error_msg
            self.log_to_csv(log_data)
            if filepath.exists():
                filepath.unlink()
            return False

    def download_all(self, retry_mode=False, folder_id=None, overall_progress_callback=None):
        """
        Download all videos. overall_progress_callback(completed, total) called after each video.
        Returns dict with counts: successful, failed, skipped, retry.
        """
        if retry_mode:
            videos = self.get_retry_videos()
        elif folder_id:
            videos = self.get_videos_from_folder(folder_id)
        else:
            videos = self.get_user_videos()

        if not videos:
            self._log("❌ No videos found")
            return {'successful': 0, 'failed': 0, 'skipped': 0, 'retry': 0}

        videos_to_download = videos
        if not retry_mode and self.testing_mode and self.max_videos:
            videos_to_download = videos[:self.max_videos]
            self._log(f"⚠️  Testing mode: {len(videos_to_download)} of {len(videos)} videos")

        self._log(f"📥 Downloading {len(videos_to_download)} videos to {self.download_dir.absolute()}")

        results = []
        total = len(videos_to_download)

        if self.enable_multithreading:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_video = {
                    executor.submit(self.download_video, video, idx, total): (video, idx)
                    for idx, video in enumerate(videos_to_download, 1)
                }
                for future in as_completed(future_to_video):
                    video, idx = future_to_video[future]
                    try:
                        result = future.result()
                    except Exception as e:
                        self._log(f"❌ {video.get('name', 'Untitled')}: {str(e)}")
                        result = False
                    results.append(result)
                    if overall_progress_callback:
                        overall_progress_callback(len(results), total)
        else:
            for idx, video in enumerate(videos_to_download, 1):
                result = self.download_video(video, idx, total)
                results.append(result)
                if overall_progress_callback:
                    overall_progress_callback(idx, total)

        counts = {
            'successful': sum(1 for r in results if r is True),
            'failed': sum(1 for r in results if r is False),
            'skipped': sum(1 for r in results if r == 'skipped'),
            'retry': sum(1 for r in results if r == 'retry'),
        }

        self._log(f"\n✅ Done — {counts['successful']} downloaded, {counts['failed']} failed, "
                  f"{counts['skipped']} skipped, {counts['retry']} flagged for retry")
        return counts
