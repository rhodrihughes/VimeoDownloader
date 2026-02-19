#!/usr/bin/env python3
"""
Vimeo Video Downloader
Downloads all videos from your Vimeo account (including unlisted and private videos)
"""

import os
import sys
import requests
import json
import csv
from pathlib import Path
from urllib.parse import urlparse
from tqdm import tqdm
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# ============================================
# TESTING MODE (Set to False for production)
# ============================================
TESTING_MODE = False  # Enable to limit downloads for testing
MAX_PAGES_TO_FETCH = 2  # Only fetch first X pages (100 videos per page)
MAX_VIDEOS_TO_DOWNLOAD = 10  # Only download first X videos

# ============================================
# MULTITHREADING SETTINGS
# ============================================
ENABLE_MULTITHREADING = True  # Enable parallel downloads
MAX_CONCURRENT_DOWNLOADS = 3  # Number of simultaneous downloads (1-5 recommended)

# ============================================
# SOURCE FILE SETTINGS
# ============================================
FORCE_SOURCE_DOWNLOAD = True  # Only download source quality files
# If True, videos without source files will be flagged for retry

# ============================================
# RETRY MODE
# ============================================
RETRY_MODE = False  # Set to True to retry videos from retry_later.csv
# When enabled, ONLY videos in retry_later.csv will be downloaded
# When disabled (False), all videos from your account will be downloaded
# ============================================



class VimeoDownloader:
    def __init__(self, access_token, download_dir=None, testing_mode=False, max_pages=None, max_videos=None, quality_preference="source", enable_multithreading=False, max_workers=3, force_source=False):
        self.access_token = access_token
        self.base_url = "https://api.vimeo.com"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.vimeo.*+json;version=3.4"
        }
        
        # Testing mode settings
        self.testing_mode = testing_mode
        self.max_pages = max_pages
        self.max_videos = max_videos
        self.quality_preference = quality_preference
        self.force_source = force_source
        
        # Multithreading settings
        self.enable_multithreading = enable_multithreading
        self.max_workers = max_workers
        self.csv_lock = threading.Lock()  # Thread-safe CSV writing
        
        # Set download directory
        if download_dir:
            self.download_dir = Path(download_dir)
        else:
            self.download_dir = Path("vimeo_downloads")
        
        self.download_dir.mkdir(exist_ok=True, parents=True)
        print(f"✓ Download directory set to: {self.download_dir.absolute()}")
        
        if self.force_source:
            print(f"✓ Force source download: ENABLED (will flag videos without source)")
        else:
            print(f"✓ Quality preference: {quality_preference}")
        
        if self.enable_multithreading:
            print(f"✓ Multithreading enabled: {self.max_workers} concurrent downloads")
        
        # Initialize CSV logs
        self.csv_path = self.download_dir / "download_log.csv"
        self.retry_csv_path = self.download_dir / "retry_later.csv"
        self.init_csv_log()
        self.init_retry_csv()
        
        if self.testing_mode:
            print(f"⚠️  TESTING MODE ENABLED")
            if self.max_pages:
                print(f"   - Will fetch maximum {self.max_pages} page(s)")
            if self.max_videos:
                print(f"   - Will download maximum {self.max_videos} video(s)")
        print()
    
    def init_csv_log(self):
        """Initialize CSV log file with headers"""
        if not self.csv_path.exists():
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Video ID', 'Title', 'Folder Path', 'Upload Date', 
                    'Privacy', 'Quality Downloaded', 'Resolution', 
                    'File Size (MB)', 'Status', 'Error Message', 'Download Date'
                ])
    
    def init_retry_csv(self):
        """Initialize retry CSV file with headers"""
        if not self.retry_csv_path.exists():
            with open(self.retry_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Video ID', 'Title', 'Folder Path', 'Upload Date', 
                    'Privacy', 'Video URL', 'Reason', 'Flagged Date'
                ])
    
    def log_to_csv(self, video_data):
        """Log video download information to CSV (thread-safe)"""
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
        """Log video that needs retry to separate CSV (thread-safe)"""
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
        """Read video IDs from retry_later.csv and fetch their details"""
        if not self.retry_csv_path.exists():
            print("❌ No retry_later.csv file found")
            return []
        
        print("📋 Reading videos from retry_later.csv...")
        
        retry_video_ids = []
        with open(self.retry_csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                video_id = row.get('Video ID')
                if video_id:
                    retry_video_ids.append(video_id)
        
        if not retry_video_ids:
            print("❌ No videos found in retry_later.csv")
            return []
        
        print(f"✓ Found {len(retry_video_ids)} videos to retry\n")
        print("📡 Fetching video details from Vimeo API...")
        
        videos = []
        with tqdm(total=len(retry_video_ids), desc="Fetching retry videos", unit="video") as pbar:
            for video_id in retry_video_ids:
                try:
                    url = f"{self.base_url}/videos/{video_id}"
                    params = {"fields": "uri,name,description,privacy,download,files,created_time,parent_folder"}
                    response = requests.get(url, headers=self.headers, params=params)
                    
                    if response.status_code == 200:
                        video_data = response.json()
                        videos.append(video_data)
                    else:
                        tqdm.write(f"⚠️  Could not fetch video {video_id}: {response.status_code}")
                except Exception as e:
                    tqdm.write(f"⚠️  Error fetching video {video_id}: {str(e)}")
                
                pbar.update(1)
        
        print(f"✓ Successfully fetched {len(videos)} videos\n")
        return videos
    
    def remove_from_retry_csv(self, video_id):
        """Remove a video from retry_later.csv after successful download (thread-safe)"""
        with self.csv_lock:
            if not self.retry_csv_path.exists():
                return
            
            # Read all rows except the one to remove
            rows_to_keep = []
            with open(self.retry_csv_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                fieldnames = reader.fieldnames
                for row in reader:
                    if row.get('Video ID') != video_id:
                        rows_to_keep.append(row)
            
            # Write back the remaining rows
            with open(self.retry_csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows_to_keep)
    
    def get_user_folders(self):
        """Fetch all folders (projects) from the authenticated user's account"""
        folders = []
        page = 1
        per_page = 100
        
        print("📡 Fetching your folders from Vimeo API...")
        
        with tqdm(desc="Fetching folders", unit=" pages", bar_format='{l_bar}{bar}| {n_fmt} pages') as pbar:
            while True:
                url = f"{self.base_url}/me/projects"
                params = {
                    "page": page,
                    "per_page": per_page,
                    "fields": "uri,name"
                }
                
                response = requests.get(url, headers=self.headers, params=params)
                
                if response.status_code != 200:
                    print(f"\n❌ Error fetching folders: {response.status_code}")
                    break
                
                data = response.json()
                folders.extend(data.get("data", []))
                
                # Check if there are more pages
                paging = data.get("paging", {})
                if not paging.get("next"):
                    break
                
                page += 1
                pbar.update(1)
                pbar.set_postfix_str(f"{len(folders)} folders found")
        
        return folders
    
    def get_videos_from_folder(self, folder_id):
        """Fetch all videos from a specific folder"""
        videos = []
        page = 1
        per_page = 100
        
        print(f"📡 Step 1: Fetching videos from folder...")
        
        with tqdm(desc="Fetching videos", unit=" pages", bar_format='{l_bar}{bar}| {n_fmt} pages') as pbar:
            while True:
                # Check if we've reached the page limit in testing mode
                if self.testing_mode and self.max_pages and page > self.max_pages:
                    print(f"\n⚠️  Reached testing limit of {self.max_pages} page(s)")
                    break
                
                url = f"{self.base_url}/me/projects/{folder_id}/videos"
                params = {
                    "page": page,
                    "per_page": per_page,
                    "fields": "uri,name,description,privacy,download,files,created_time,parent_folder"
                }
                
                response = requests.get(url, headers=self.headers, params=params)
                
                if response.status_code != 200:
                    print(f"\n❌ Error fetching videos: {response.status_code}")
                    print(response.text)
                    break
                
                data = response.json()
                videos.extend(data.get("data", []))
                
                # Check if there are more pages
                paging = data.get("paging", {})
                if not paging.get("next"):
                    break
                
                page += 1
                pbar.update(1)
                pbar.set_postfix_str(f"{len(videos)} videos found")
        
        print(f"✓ Found {len(videos)} videos in this folder\n")
        return videos

    def get_user_videos(self):
        """Fetch all videos from the authenticated user's account"""
        videos = []
        page = 1
        per_page = 100
        
        print("📡 Step 1: Fetching your videos from Vimeo API...")
        
        with tqdm(desc="Fetching videos", unit=" pages", bar_format='{l_bar}{bar}| {n_fmt} pages') as pbar:
            while True:
                # Check if we've reached the page limit in testing mode
                if self.testing_mode and self.max_pages and page > self.max_pages:
                    print(f"\n⚠️  Reached testing limit of {self.max_pages} page(s)")
                    break
                
                url = f"{self.base_url}/me/videos"
                params = {
                    "page": page,
                    "per_page": per_page,
                    "fields": "uri,name,description,privacy,download,files,created_time,parent_folder"
                }
                
                response = requests.get(url, headers=self.headers, params=params)
                
                if response.status_code != 200:
                    print(f"\n❌ Error fetching videos: {response.status_code}")
                    print(response.text)
                    break
                
                data = response.json()
                videos.extend(data.get("data", []))
                
                # Check if there are more pages
                paging = data.get("paging", {})
                if not paging.get("next"):
                    break
                
                page += 1
                pbar.update(1)
                pbar.set_postfix_str(f"{len(videos)} videos found")
        
        print(f"✓ Found {len(videos)} videos in your account\n")
        return videos

    def get_folder_path(self, video):
        """Get the folder path for a video to emulate Vimeo's folder structure"""
        folder_path = []
        parent_folder = video.get("parent_folder")
        
        if parent_folder and parent_folder.get("uri"):
            folder_uri = parent_folder.get("uri")
            folder_id = folder_uri.split("/")[-1]
            
            try:
                # Fetch folder details
                url = f"{self.base_url}/me/projects/{folder_id}"
                response = requests.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    folder_data = response.json()
                    folder_name = folder_data.get("name", f"folder_{folder_id}")
                    folder_path.append(self.sanitize_filename(folder_name))
            except:
                pass
        
        return "/".join(folder_path) if folder_path else ""
    
    def get_download_link_by_quality(self, video):
        """Get download link based on quality preference or force source"""
        video_id = video["uri"].split("/")[-1]
        
        # Try to get download links
        download_links = video.get("download", [])
        
        if not download_links:
            # If no download links in the initial response, fetch them separately
            url = f"{self.base_url}/videos/{video_id}"
            params = {"fields": "download,files"}
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                video_data = response.json()
                download_links = video_data.get("download", [])
        
        if download_links:
            # Sort by quality (height) descending
            download_links.sort(key=lambda x: x.get("height", 0), reverse=True)
            
            # If forcing source, check if source quality is available
            if self.force_source:
                # Look for "source" quality specifically
                source_link = None
                for link in download_links:
                    if link.get("quality") == "source":
                        source_link = link
                        break
                
                if source_link:
                    return source_link
                else:
                    # No source file available - return None with special flag
                    return {"error": "no_source", "available_qualities": [l.get("quality") for l in download_links]}
            
            # Quality preference logic (non-forced mode)
            if self.quality_preference == "source":
                # Get the highest quality (source)
                return download_links[0]
            elif self.quality_preference == "1080p":
                # Try to find 1080p, fallback to closest
                for link in download_links:
                    if link.get("height") == 1080:
                        return link
                return download_links[0]  # Fallback to best
            elif self.quality_preference == "720p":
                # Try to find 720p, fallback to closest
                for link in download_links:
                    if link.get("height") == 720:
                        return link
                return download_links[0]  # Fallback to best
            elif self.quality_preference == "540p":
                # Try to find 540p, fallback to closest
                for link in download_links:
                    if link.get("height") == 540:
                        return link
                return download_links[0]  # Fallback to best
            else:
                # Default to highest quality
                return download_links[0]
        
        # Fallback to files if download is not available
        files = video.get("files", [])
        if files:
            # Filter for video files and sort by quality
            video_files = [f for f in files if f.get("quality") != "hls"]
            if video_files:
                video_files.sort(key=lambda x: x.get("height", 0), reverse=True)
                return video_files[0]
        
        return None
    
    def sanitize_filename(self, filename):
        """Remove invalid characters from filename"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")
        return filename
    
    def download_video(self, video, index, total):
        """Download a single video"""
        video_name = video.get("name", "Untitled")
        video_id = video["uri"].split("/")[-1]
        privacy = video.get('privacy', {}).get('view', 'unknown')
        upload_date = video.get('created_time', 'Unknown')
        
        # Parse upload date
        if upload_date != 'Unknown':
            try:
                upload_date = datetime.fromisoformat(upload_date.replace('Z', '+00:00')).strftime('%Y-%m-%d')
            except:
                pass
        
        # Get folder path
        folder_path = self.get_folder_path(video)
        
        if not self.enable_multithreading:
            print(f"\n{'='*70}")
            print(f"📹 Video {index}/{total}: {video_name}")
            print(f"   ID: {video_id} | Privacy: {privacy} | Uploaded: {upload_date}")
            if folder_path:
                print(f"   📁 Folder: {folder_path}")
        
        # Prepare CSV log data
        log_data = {
            'video_id': video_id,
            'title': video_name,
            'folder_path': folder_path,
            'upload_date': upload_date,
            'privacy': privacy,
            'quality': '',
            'resolution': '',
            'file_size_mb': '',
            'status': 'Failed',
            'error_message': ''
        }
        
        # Get download link
        if not self.enable_multithreading:
            print(f"   🔍 Step 1: Fetching download link...")
        
        download_info = self.get_download_link_by_quality(video)
        
        # Check if source file is not available (when forcing source)
        if isinstance(download_info, dict) and download_info.get("error") == "no_source":
            error_msg = f"Source file not available. Available qualities: {', '.join(download_info.get('available_qualities', []))}"
            
            if not self.enable_multithreading:
                print(f"   ⚠️  {error_msg}")
                print(f"   📝 Flagged for retry later")
            
            # Log to retry CSV
            video_url = f"https://vimeo.com/{video_id}"
            retry_data = {
                'video_id': video_id,
                'title': video_name,
                'folder_path': folder_path,
                'upload_date': upload_date,
                'privacy': privacy,
                'video_url': video_url,
                'reason': error_msg
            }
            self.log_to_retry_csv(retry_data)
            
            # Also log to main CSV
            log_data['error_message'] = error_msg
            log_data['status'] = 'Retry Later (No Source)'
            self.log_to_csv(log_data)
            return 'retry'
        
        if not download_info:
            error_msg = "No download link available for this video"
            if not self.enable_multithreading:
                print(f"   ⚠️  {error_msg}")
            log_data['error_message'] = error_msg
            self.log_to_csv(log_data)
            return False
        
        download_url = download_info.get("link")
        quality = download_info.get("quality", "unknown")
        height = download_info.get("height", "unknown")
        size_mb = download_info.get("size", 0) / (1024 * 1024)
        
        log_data['quality'] = quality
        log_data['resolution'] = f"{height}p"
        log_data['file_size_mb'] = f"{size_mb:.2f}"
        
        if not download_url:
            error_msg = "Could not find download URL"
            print(f"   ⚠️  {error_msg}")
            log_data['error_message'] = error_msg
            self.log_to_csv(log_data)
            return False
        
        print(f"   ✓ Found download link")
        print(f"   📊 Quality: {quality} ({height}p) | Size: {size_mb:.1f} MB")
        
        # Create folder structure
        if folder_path:
            video_dir = self.download_dir / folder_path
            video_dir.mkdir(exist_ok=True, parents=True)
        else:
            video_dir = self.download_dir
        
        # Create filename
        safe_name = self.sanitize_filename(video_name)
        extension = download_info.get("type", "video/mp4").split("/")[-1]
        filename = f"{video_id}_{safe_name}.{extension}"
        filepath = video_dir / filename
        
        # Skip if already downloaded
        if filepath.exists():
            print(f"   ✓ Already downloaded, skipping")
            log_data['status'] = 'Skipped (Already exists)'
            self.log_to_csv(log_data)
            return True
        
        # Download the video
        try:
            print(f"   💾 Step 2: Downloading...")
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            
            total_size = int(response.headers.get("content-length", 0))
            
            with open(filepath, "wb") as f:
                with tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f"   Progress",
                    bar_format='{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{rate_fmt}]'
                ) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            
            relative_path = str(filepath.relative_to(self.download_dir))
            if not self.enable_multithreading:
                print(f"   ✅ Downloaded successfully to: {relative_path}")
            log_data['status'] = 'Success'
            self.log_to_csv(log_data)
            
            # Remove from retry CSV if it was a retry download
            self.remove_from_retry_csv(video_id)
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"   ❌ Error downloading: {error_msg}")
            log_data['error_message'] = error_msg
            self.log_to_csv(log_data)
            if filepath.exists():
                filepath.unlink()
            return False

    def download_all(self, retry_mode=False, folder_id=None):
        """Download all videos from the account, a specific folder, or retry failed videos"""
        if retry_mode:
            print("🔄 RETRY MODE: Downloading videos from retry_later.csv\n")
            videos = self.get_retry_videos()
        elif folder_id:
            videos = self.get_videos_from_folder(folder_id)
        else:
            videos = self.get_user_videos()
        
        if not videos:
            print("❌ No videos found or error occurred")
            return
        
        # Limit videos in testing mode (only for non-retry mode)
        videos_to_download = videos
        if not retry_mode and self.testing_mode and self.max_videos:
            videos_to_download = videos[:self.max_videos]
            print(f"⚠️  Testing mode: Limiting to first {len(videos_to_download)} of {len(videos)} videos\n")
        
        step_num = "Step 2" if not retry_mode else "Step 1"
        print(f"📥 {step_num}: Starting download of {len(videos_to_download)} videos...")
        print(f"📂 Saving to: {self.download_dir.absolute()}\n")
        
        if self.enable_multithreading:
            results = self._download_multithreaded(videos_to_download)
        else:
            results = self._download_sequential(videos_to_download)
        
        # Count results
        successful = sum(1 for r in results if r == 'success')
        failed = sum(1 for r in results if r == 'failed')
        skipped = sum(1 for r in results if r == 'skipped')
        retry = sum(1 for r in results if r == 'retry')
        
        print("\n" + "="*70)
        print("� DOWNLlOAD SUMMARY")
        print("="*70)
        if self.testing_mode and self.max_videos and len(videos) > self.max_videos:
            print(f"  Total videos in account: {len(videos)}")
            print(f"  Videos processed (testing): {len(videos_to_download)}")
        else:
            print(f"  Total videos found: {len(videos_to_download)}")
        print(f"  ✅ Successfully downloaded: {successful}")
        print(f"  ❌ Failed: {failed}")
        print(f"  ⏭️  Skipped (already exists): {skipped}")
        
        if retry > 0:
            print(f"  🔄 Flagged for retry (no source): {retry}")
            print(f"\n📝 Retry list saved to: {self.retry_csv_path}")
            print(f"   These videos don't have source files available yet.")
            print(f"   Run the script again later to retry downloading them.")
        
        print(f"\n📂 All videos saved to: {self.download_dir.absolute()}")
        print(f"📄 Download log: {self.csv_path}")
        print("="*70)
    
    def _download_sequential(self, videos):
        """Download videos one at a time"""
        results = []
        for index, video in enumerate(videos, 1):
            result = self.download_video(video, index, len(videos))
            if result is True:
                results.append('success')
            elif result is False:
                results.append('failed')
            elif result == 'retry':
                results.append('retry')
            else:
                results.append('skipped')
        return results
    
    def _download_multithreaded(self, videos):
        """Download videos using multiple threads"""
        print(f"🚀 Using {self.max_workers} concurrent downloads\n")
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_video = {
                executor.submit(self.download_video, video, idx, len(videos)): (video, idx)
                for idx, video in enumerate(videos, 1)
            }
            
            # Process completed downloads with progress bar
            with tqdm(total=len(videos), desc="Overall Progress", unit="video") as pbar:
                for future in as_completed(future_to_video):
                    video, idx = future_to_video[future]
                    try:
                        result = future.result()
                        video_name = video.get("name", "Untitled")
                        
                        if result is True:
                            tqdm.write(f"✅ [{idx}/{len(videos)}] {video_name}")
                            results.append('success')
                        elif result is False:
                            tqdm.write(f"❌ [{idx}/{len(videos)}] {video_name}")
                            results.append('failed')
                        elif result == 'retry':
                            tqdm.write(f"🔄 [{idx}/{len(videos)}] {video_name} (no source - retry later)")
                            results.append('retry')
                        else:
                            tqdm.write(f"⏭️  [{idx}/{len(videos)}] {video_name} (skipped)")
                            results.append('skipped')
                    except Exception as e:
                        video_name = video.get("name", "Untitled")
                        tqdm.write(f"❌ [{idx}/{len(videos)}] {video_name} - Error: {str(e)}")
                        results.append('failed')
                    
                    pbar.update(1)
        
        return results


def main():
    print("="*70)
    print("🎬 VIMEO VIDEO DOWNLOADER")
    print("="*70)
    print()
    
    # Check if retry mode is enabled
    if RETRY_MODE:
        print("🔄 RETRY MODE ENABLED")
        print("   Will only download videos from retry_later.csv\n")
    
    # Get access token
    print("🔑 API KEY REQUIRED")
    print("-"*70)
    print("Enter your Vimeo API access token.")
    print("Get one at: https://developer.vimeo.com/apps\n")

    access_token = input("Enter your Vimeo access token: ").strip()

    if not access_token:
        print("\n❌ Error: No access token provided")
        return
    
    # Get download directory
    print("\n" + "-"*70)
    print("📂 DOWNLOAD LOCATION (Required)")
    print("-"*70)
    print("Select where to save the videos:")
    print("1. Type or drag & drop a folder path")
    print("2. Type 'browse' to open a folder picker dialog\n")
    
    download_path = None
    
    while not download_path:
        user_input = input("Download path (or 'browse'): ").strip()
        
        if not user_input:
            print("❌ Download location is required. Please enter a path or type 'browse'.\n")
            continue
        
        # Handle browse option
        if user_input.lower() == 'browse':
            print("\n🔍 Opening folder picker dialog...")
            try:
                root = tk.Tk()
                root.withdraw()  # Hide the main window
                root.attributes('-topmost', True)  # Bring dialog to front
                
                folder_selected = filedialog.askdirectory(
                    title="Select Download Folder",
                    initialdir=os.path.expanduser("~")
                )
                root.destroy()
                
                if folder_selected:
                    download_path = folder_selected
                    print(f"✓ Folder selected: {download_path}")
                else:
                    print("❌ No folder selected. Please try again.\n")
            except Exception as e:
                print(f"⚠️  Could not open folder picker: {e}")
                print("Please enter a path manually instead.\n")
        else:
            # Clean up dragged path (remove quotes and escape characters)
            user_input = user_input.strip("'\"").replace("\\ ", " ")
            user_input = os.path.expanduser(user_input)  # Expand ~ to home directory
            
            # Verify the path exists or can be created
            if os.path.exists(user_input) and not os.path.isdir(user_input):
                print(f"❌ Path exists but is not a directory: {user_input}")
                print("Please enter a valid folder path.\n")
            else:
                download_path = user_input
                print(f"✓ Custom path selected: {download_path}")
    
    # Initialize downloader to fetch folders
    print("\n" + "="*70)
    print("📂 FOLDER SELECTION (Optional)")
    print("="*70)
    print("Fetching your folders...\n")
    
    temp_downloader = VimeoDownloader(
        access_token,
        testing_mode=TESTING_MODE,
        max_pages=MAX_PAGES_TO_FETCH if TESTING_MODE else None,
        max_videos=MAX_VIDEOS_TO_DOWNLOAD if TESTING_MODE else None,
        quality_preference="source",
        enable_multithreading=ENABLE_MULTITHREADING,
        max_workers=MAX_CONCURRENT_DOWNLOADS,
        force_source=FORCE_SOURCE_DOWNLOAD
    )
    
    folders = temp_downloader.get_user_folders()
    selected_folder_id = None
    
    if folders:
        print(f"Found {len(folders)} folder(s):\n")
        for idx, folder in enumerate(folders, 1):
            folder_name = folder.get("name", "Untitled")
            folder_id = folder["uri"].split("/")[-1]
            print(f"  {idx}. {folder_name}")
        
        print(f"  0. Download ALL videos (not from a specific folder)")
        print("\nPress Enter to download all videos\n")
        
        choice = input("Select folder (0 or Enter for all, or number): ").strip()
        
        if choice and choice != "0":
            try:
                folder_idx = int(choice) - 1
                if 0 <= folder_idx < len(folders):
                    selected_folder = folders[folder_idx]
                    selected_folder_id = selected_folder["uri"].split("/")[-1]
                    selected_folder_name = selected_folder.get("name", "Untitled")
                    print(f"✓ Selected folder: {selected_folder_name}\n")
                else:
                    print("❌ Invalid selection. Downloading all videos.\n")
            except ValueError:
                print("❌ Invalid input. Downloading all videos.\n")
    else:
        print("⚠️  No folders found in your account.\n")
    # Get quality preference
    print("\n" + "-"*70)
    print("🎥 VIDEO QUALITY PREFERENCE")
    print("-"*70)
    print("Select the video quality to download:")
    print("1. Source (highest quality available) - Default")
    print("2. 1080p")
    print("3. 720p")
    print("4. 540p")
    print("\nPress Enter for Source quality\n")
    
    quality_choice = input("Quality choice (1-4 or Enter): ").strip()
    
    quality_map = {
        "1": "source",
        "2": "1080p",
        "3": "720p",
        "4": "540p",
        "": "source"
    }
    
    quality_preference = quality_map.get(quality_choice, "source")
    print(f"✓ Quality selected: {quality_preference}")
    
    print("\n" + "="*70)
    print("🚀 STARTING DOWNLOAD PROCESS")
    print("="*70 + "\n")
    
    try:
        downloader = VimeoDownloader(
            access_token, 
            download_path,
            testing_mode=TESTING_MODE,
            max_pages=MAX_PAGES_TO_FETCH if TESTING_MODE else None,
            max_videos=MAX_VIDEOS_TO_DOWNLOAD if TESTING_MODE else None,
            quality_preference=quality_preference,
            enable_multithreading=ENABLE_MULTITHREADING,
            max_workers=MAX_CONCURRENT_DOWNLOADS,
            force_source=FORCE_SOURCE_DOWNLOAD
        )
        downloader.download_all(retry_mode=RETRY_MODE, folder_id=selected_folder_id)
        
        print(f"\n📊 Download log saved to: {downloader.csv_path}")
        
        if RETRY_MODE:
            # Check if retry CSV is now empty
            retry_count = 0
            if downloader.retry_csv_path.exists():
                with open(downloader.retry_csv_path, 'r', newline='', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    retry_count = sum(1 for _ in reader)
            
            if retry_count == 0:
                print(f"🎉 All retry videos have been processed!")
                print(f"   The retry_later.csv file is now empty.")
            else:
                print(f"⚠️  {retry_count} video(s) still need retry")
                print(f"   Check retry_later.csv for details.")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Download interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")


if __name__ == "__main__":
    main()
