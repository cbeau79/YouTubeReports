# youtube_utils.py
import os
import ast
import json
import googleapiclient.discovery
from urllib.parse import urlparse, parse_qs
import isodate
import requests
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from config import Config
import logging
import yt_dlp
from pathlib import Path
import stat
import shutil
import tempfile
import fcntl
from cookie_manager import CookieValidator
from contextlib import contextmanager

# Use configuration values
API_KEY = Config.YOUTUBE_API_KEY # os.environ.get('YOUTUBE_API_KEY')
OPENAI_API_KEY = Config.OPENAI_API_KEY # os.environ.get('OPENAI_API_KEY')
MAX_VIDEOS = Config.MAX_VIDEOS_TO_FETCH # app_config['max_videos_to_fetch']
MAX_VIDEOS_FOR_SUBTITLES = Config.MAX_VIDEOS_FOR_SUBTITLES # app_config['max_videos_for_subtitles']
OPENAI_MODEL = Config.OPENAI_MODEL # app_config['openai_model']
MAX_TOKENS = Config.MAX_TOKENS # app_config['max_tokens']
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_cookies.txt")

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize YouTube API client
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

def extract_channel_id(url):
    """
    Extract channel ID from a YouTube channel URL only.
    Returns None for video URLs or invalid URLs.
    """
    parsed_url = urlparse(url)
    
    if 'youtube.com' in parsed_url.netloc or 'youtu.be' in parsed_url.netloc:
        path = parsed_url.path
        
        # Only handle direct channel URL patterns
        if path.startswith('/@'):
            # Handle @username format
            username = path[2:]  # Remove the leading '/@'
            try:
                channel_response = youtube.search().list(
                    part="snippet",
                    q=username,
                    type="channel",
                    maxResults=1
                ).execute()
                if 'items' in channel_response and channel_response['items']:
                    return channel_response['items'][0]['snippet']['channelId']
            except Exception as e:
                logging.error(f"Error fetching channel ID for @{username}: {e}")
                return None
        elif path.startswith('/channel/'):
            # Direct channel ID format
            return path.split('/')[2]
        elif path.startswith('/c/') or path.startswith('/user/'):
            # Custom URL format
            custom_name = path.split('/')[2]
            try:
                channel_response = youtube.search().list(
                    part="snippet",
                    q=custom_name,
                    type="channel",
                    maxResults=1
                ).execute()
                if 'items' in channel_response and channel_response['items']:
                    return channel_response['items'][0]['snippet']['channelId']
            except Exception as e:
                logging.error(f"Error fetching channel ID for {custom_name}: {e}")
                return None
    
    return None

def get_video_data(video_id, include_comments=False):
    output = []

    try:
        video_response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=video_id
        ).execute()

        for video in video_response['items']:
            duration = video['contentDetails'].get('duration', 'PT0S')
            try:
                duration_seconds = isodate.parse_duration(duration).total_seconds()
            except isodate.ISO8601Error:
                duration_seconds = 0

            subtitles = get_video_subtitles(video_id)

            if subtitles:
                logging.info(f"Retrieved subtitles for video: {video['snippet']['title']}")
            else:
                logging.warning(f"No subtitles available for video: {video['snippet']['title']}")
                return None  # Return None if subtitles are not available

            video_data = {
                'title': video['snippet']['title'],
                'description': video['snippet']['description'],
                'length': int(duration_seconds),
                'date_published': video['snippet']['publishedAt'],
                'tags': video['snippet'].get('tags', []),
                'youtube_video_id': video['id'],
                'youtube_category_id': video['snippet'].get('categoryId', 'Unknown'),
                'views': int(video['statistics'].get('viewCount', 0)),
                'like_count': int(video['statistics'].get('likeCount', 0)),
                'comment_count': int(video['statistics'].get('commentCount', 0)),
                'thumbnail_url': video['snippet']['thumbnails']['default']['url'],
                'channel_title': video['snippet']['channelTitle'],
                'subtitles': subtitles
            }

            if include_comments:
                video_data['top_comments'] = get_video_comments(video_id)

            output.append(video_data)

        return output

    except Exception as e:
        logging.error(f"Error in get_video_data for video {video_id}: {str(e)}")
        return None

def get_video_comments(video_id, max_results=100):
    comments = []
    next_page_token = None

    while len(comments) < max_results:
        try:
            response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=min(100, max_results - len(comments)),
                order="relevance",
                pageToken=next_page_token
            ).execute()

            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                comments.append({
                    'author': comment['authorDisplayName'],
                    'text': comment['textDisplay'],
                    'likes': comment['likeCount'],
                    'published_at': comment['publishedAt']
                })

            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        except googleapiclient.errors.HttpError as e:
            print(f"An HTTP error occurred while fetching comments: {e}")
            break

    return comments[:max_results]

def extract_video_id(url):
    parsed_url = urlparse(url)
    if parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
        if parsed_url.path[:7] == '/embed/':
            return parsed_url.path.split('/')[2]
        if parsed_url.path[:3] == '/v/':
            return parsed_url.path.split('/')[2]
    return None  # Invalid YouTube URL

def get_channel_videos(channel_id, max_results):
    videos = []
    next_page_token = None

    while len(videos) < max_results:
        request = youtube.search().list(
            part="id,snippet",
            channelId=channel_id,
            maxResults=min(50, max_results - len(videos)),
            order="date",
            type="video",
            pageToken=next_page_token
        )
        response = request.execute()

        video_ids = [item['id']['videoId'] for item in response['items']]
        videos_response = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=','.join(video_ids)
        ).execute()

        for video in videos_response['items']:
            duration = video['contentDetails'].get('duration', 'PT0S')
            try:
                duration_seconds = isodate.parse_duration(duration).total_seconds()
            except isodate.ISO8601Error:
                duration_seconds = 0
            
            width = video['snippet']['thumbnails']['default']['width']
            height = video['snippet']['thumbnails']['default']['height']
            is_vertical = height > width
            is_short = duration_seconds <= 60 and is_vertical

            if not is_short:
                videos.append({
                    'title': video['snippet']['title'],
                    'description': video['snippet']['description'],
                    'length': int(duration_seconds),
                    'date_published': video['snippet']['publishedAt'],
                    'tags': video['snippet'].get('tags', []),
                    'youtube_video_id': video['id'],
                    'youtube_category_id': video['snippet'].get('categoryId', 'Unknown'),
                    'views': int(video['statistics'].get('viewCount', 0)),
                    'like_count': int(video['statistics'].get('likeCount', 0)),
                    'comment_count': int(video['statistics'].get('commentCount', 0)),
                    'thumbnail_url': video['snippet']['thumbnails']['default']['url'],
                    'channel_title': video['snippet']['channelTitle']
                })

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return videos[:max_results]

# ---
# SUBTITLE FUNCTIONS
# ---

class CookieManager:
    def __init__(self, cookie_file):
        # Convert to absolute path
        self.cookie_file = os.path.abspath(cookie_file)
        # Store the directory the cookie file is in
        self.original_dir = os.path.dirname(self.cookie_file)
        self.lock_file = f"{cookie_file}.lock"
        self.backup_file = f"{cookie_file}.backup"

    @contextmanager
    def file_lock(self):
        """Context manager for file locking."""
        lock_fd = open(self.lock_file, 'w')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def create_temp_copy(self):
        """Create an isolated environment with cookie file."""
        try:
            with self.file_lock():
                logging.info(f"Original cookie file location: {self.cookie_file}")
                logging.info(f"Original directory: {self.original_dir}")

                # Create isolated directory structure far from original
                base_temp = tempfile.gettempdir()
                temp_dir = os.path.join(base_temp, f'yt_cookies_{os.getpid()}')
                cookies_dir = os.path.join(temp_dir, 'youtube', 'cookies')
                os.makedirs(cookies_dir, exist_ok=True)
                
                temp_cookie_file = os.path.join(cookies_dir, 'cookies.txt')
                logging.info(f"Temporary cookie file location: {temp_cookie_file}")

                # Create backup if it doesn't exist
                if not os.path.exists(self.backup_file):
                    shutil.copy2(self.cookie_file, self.backup_file)
                    os.chmod(self.backup_file, stat.S_IRUSR)
                    logging.info(f"Created backup cookie file: {self.backup_file}")

                # Temporarily move original out of the way
                temp_original = f"{self.cookie_file}.original"
                if os.path.exists(self.cookie_file):
                    os.rename(self.cookie_file, temp_original)
                    logging.info(f"Moved original cookie file to: {temp_original}")

                # Copy from backup to temp location
                shutil.copy2(self.backup_file, temp_cookie_file)
                os.chmod(temp_cookie_file, stat.S_IRUSR | stat.S_IWUSR)
                
                return temp_cookie_file, temp_dir

        except Exception as e:
            logging.error(f"Error in create_temp_copy: {str(e)}")
            # Restore original if something went wrong
            if 'temp_original' in locals() and os.path.exists(temp_original):
                os.rename(temp_original, self.cookie_file)
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            return None, None

    def cleanup(self, temp_file, temp_dir):
        """Clean up temporary files and restore original."""
        try:
            if temp_file and os.path.exists(temp_file):
                logging.info(f"Cleaning up temp cookie file: {temp_file}")
                os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)
                os.remove(temp_file)

            if temp_dir and os.path.exists(temp_dir):
                logging.info(f"Cleaning up temp directory: {temp_dir}")
                for root, dirs, files in os.walk(temp_dir):
                    for d in dirs:
                        os.chmod(os.path.join(root, d), stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
                    for f in files:
                        os.chmod(os.path.join(root, f), stat.S_IRUSR | stat.S_IWUSR)
                shutil.rmtree(temp_dir)

            # Restore original file
            temp_original = f"{self.cookie_file}.original"
            if os.path.exists(temp_original):
                logging.info(f"Restoring original cookie file from: {temp_original}")
                os.rename(temp_original, self.cookie_file)

        except Exception as e:
            logging.error(f"Error in cleanup: {str(e)}")

def get_yt_dlp_opts(temp_cookie_file, temp_dir):
    """Get yt-dlp options with enhanced anti-bot-detection measures."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(temp_cookie_file)))
    return {
        'quiet': True,
        'no_warnings': True,
        'no_color': True,
        'cookiefile': temp_cookie_file,
        'no_write_download_archive': True,
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'en-US'],
        'subtitlesformat': 'vtt',
        'updatetime': False,
        'no_cache_dir': True,
        'paths': {'home': base_dir},
        'cookiesfrombrowser': None,
        'no_config': True,
        'extract_flat': True,
        'socket_timeout': 30,
        'retries': 5,
        'fragment_retries': 5,
        'retry_sleep': 5,
        'sleep_interval': 2,
        'max_sleep_interval': 5,
        'ignoreerrors': True,
        'no_playlist': True,
        # Enhanced browser emulation
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'http_headers': {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'TE': 'trailers'
        }
    }

'''def get_video_subtitles(video_id):
    """Enhanced subtitle fetching with better error handling and retry logic."""
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    cookie_manager = CookieManager(COOKIE_FILE)
    temp_cookie_file, temp_dir = cookie_manager.create_temp_copy()
    
    if not temp_cookie_file:
        logging.error("Failed to create temporary cookie file")
        return None
    
    try:
        logging.info("=== Starting subtitle extraction ===")
        
        cookie_validator = CookieValidator(temp_cookie_file)
        is_valid, message = cookie_validator.check_status()
        
        if not is_valid:
            logging.error(f"Cookie validation failed: {message}")
            # Try fallback method for subtitles
            return get_subtitles_fallback(video_id)

        with tempfile.TemporaryDirectory() as subtitles_temp_dir:
            logging.info(f"Using subtitles temp dir: {subtitles_temp_dir}")
            ydl_opts = get_yt_dlp_opts(temp_cookie_file, temp_dir)
            ydl_opts['outtmpl'] = os.path.join(subtitles_temp_dir, '%(id)s.%(ext)s')
            
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(video_url, download=False)
                        
                        # Check for available subtitles
                        has_subtitles = ('subtitles' in info and ('en' in info['subtitles'] or 'en-US' in info['subtitles'])) or \
                                      ('automatic_captions' in info and ('en' in info['automatic_captions'] or 'en-US' in info['automatic_captions']))
                        
                        if has_subtitles:
                            logging.info("Downloading subtitles...")
                            ydl.download([video_url])
                            
                            # Try multiple subtitle file variations
                            subtitle_variations = [
                                f"{video_id}.en.vtt",
                                f"{video_id}.en-US.vtt",
                                f"{video_id}.en-GB.vtt",
                                f"{video_id}.en-AUTO.vtt"
                            ]
                            
                            for subtitle_file in subtitle_variations:
                                full_path = os.path.join(subtitles_temp_dir, subtitle_file)
                                if os.path.exists(full_path):
                                    with open(full_path, 'r', encoding='utf-8') as f:
                                        return clean_subtitle_text(f.read())
                            
                            logging.warning("No subtitle files found after download")
                            return get_subtitles_fallback(video_id)
                            
                except Exception as e:
                    retry_count += 1
                    if retry_count < max_retries:
                        logging.warning(f"Attempt {retry_count} failed, retrying... Error: {str(e)}")
                        time.sleep(2 ** retry_count)  # Exponential backoff
                    else:
                        logging.error(f"All attempts failed. Error: {str(e)}")
                        return get_subtitles_fallback(video_id)
                        
            return None

    except Exception as e:
        logging.error(f"Error in subtitle extraction: {str(e)}")
        return get_subtitles_fallback(video_id)
        
    finally:
        logging.info("=== Cleaning up ===")
        cookie_manager.cleanup(temp_cookie_file, temp_dir)'''

def get_video_subtitles(video_id):
    """Multi-tiered approach to subtitle fetching with multiple fallbacks."""
    logging.info(f"=== Starting subtitle extraction for video {video_id} ===")
    
    # Try all methods in sequence until one works
    subtitle_text = (
        try_youtube_transcript_api(video_id) or
        try_yt_dlp_with_cookies(video_id) or
        try_yt_dlp_no_cookies(video_id) or
        try_direct_request(video_id)
    )
    
    if subtitle_text:
        return clean_subtitle_text(subtitle_text)
    return None

def try_youtube_transcript_api(video_id):
    """Try getting transcripts using youtube_transcript_api first."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.formatters import TextFormatter
        
        logging.info("Attempting to fetch subtitles using YouTube Transcript API...")
        
        # Try multiple language variants
        for lang in ['en', 'en-US', 'en-GB', 'a.en']:
            try:
                transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                formatter = TextFormatter()
                return formatter.format_transcript(transcript)
            except Exception as e:
                logging.debug(f"Failed to get {lang} transcript: {str(e)}")
                continue
                
        return None
    except Exception as e:
        logging.warning(f"YouTube Transcript API attempt failed: {str(e)}")
        return None

def try_yt_dlp_with_cookies(video_id):
    """Try yt-dlp with cookies approach."""
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    cookie_manager = CookieManager(COOKIE_FILE)
    temp_cookie_file, temp_dir = cookie_manager.create_temp_copy()
    
    if not temp_cookie_file:
        return None
        
    try:
        logging.info("Attempting to fetch subtitles using yt-dlp with cookies...")
        with tempfile.TemporaryDirectory() as subtitles_temp_dir:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiefile': temp_cookie_file,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US'],
                'subtitlesformat': 'vtt',
                'skip_download': True,
                'outtmpl': os.path.join(subtitles_temp_dir, '%(id)s.%(ext)s'),
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'referer': 'https://www.youtube.com/',
                'http_headers': {
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate'
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([video_url])
                    for ext in ['.en.vtt', '.en-US.vtt']:
                        subtitle_file = os.path.join(subtitles_temp_dir, f"{video_id}{ext}")
                        if os.path.exists(subtitle_file):
                            with open(subtitle_file, 'r', encoding='utf-8') as f:
                                return f.read()
                except:
                    return None
                    
    finally:
        cookie_manager.cleanup(temp_cookie_file, temp_dir)
    
    return None

def try_yt_dlp_no_cookies(video_id):
    """Try yt-dlp without cookies."""
    try:
        logging.info("Attempting to fetch subtitles using yt-dlp without cookies...")
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'quiet': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US'],
                'subtitlesformat': 'vtt',
                'skip_download': True,
                'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s')
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    url = f'https://www.youtube.com/watch?v={video_id}'
                    ydl.download([url])
                    for ext in ['.en.vtt', '.en-US.vtt']:
                        subtitle_file = os.path.join(temp_dir, f"{video_id}{ext}")
                        if os.path.exists(subtitle_file):
                            with open(subtitle_file, 'r', encoding='utf-8') as f:
                                return f.read()
                except:
                    return None
    except Exception as e:
        logging.warning(f"yt-dlp without cookies attempt failed: {str(e)}")
        return None

def try_direct_request(video_id):
    """Try direct request to YouTube's subtitle endpoints."""
    try:
        logging.info("Attempting to fetch subtitles using direct request...")
        # Try to get automatic captions first
        url = f"https://www.youtube.com/api/timedtext?lang=en&v={video_id}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200 and response.text:
            # Parse XML response
            root = ET.fromstring(response.text)
            texts = []
            for text in root.findall('.//text'):
                if text.text:
                    texts.append(text.text)
            return ' '.join(texts)
    except Exception as e:
        logging.warning(f"Direct request attempt failed: {str(e)}")
        return None

def get_subtitles_fallback(video_id):
    """Fallback method to get subtitles using alternative approach."""
    try:
        # Try using YouTube's transcript API directly as fallback
        from youtube_transcript_api import YouTubeTranscriptApi
        
        transcripts = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
        if transcripts:
            # Combine all transcript pieces into one text
            full_text = ' '.join(item['text'] for item in transcripts)
            return clean_subtitle_text(full_text)
            
    except Exception as e:
        logging.error(f"Fallback subtitle extraction failed: {str(e)}")
        return None

def clean_subtitle_text(subtitle_content):
    """
    Clean subtitle content to extract only the spoken text.
    Removes all formatting, timestamps, positioning, and metadata.
    
    Args:
        subtitle_content (str): Raw subtitle content
        
    Returns:
        str: Clean spoken text only
    """
    # Remove WEBVTT header and metadata
    text = re.sub(r'WEBVTT\n.*?\n\n', '', subtitle_content, flags=re.DOTALL)
    
    # Remove positioning information (align:start position:0%)
    text = re.sub(r'align:[^\s]+ position:\d+%', '', text)
    
    # Remove timestamps in various formats:
    # Standard format: 00:00:00.000 --> 00:00:00.000
    text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}\.\d{3}', '', text)
    # Shortened format: 00:00.000 --> 00:00.000
    text = re.sub(r'\d{2}:\d{2}\.\d{3}\s*-->\s*\d{2}:\d{2}\.\d{3}', '', text)
    # Any remaining timestamp-like patterns
    text = re.sub(r'^\d{2}:\d{2}(?::\d{2})?\.\d{3}', '', text, flags=re.MULTILINE)
    
    # Remove line numbers and indices
    text = re.sub(r'^\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\n', '', text, flags=re.MULTILINE)
    
    # Remove speaker labels and cues
    text = re.sub(r'^\s*\[.*?\]\s*', '', text, flags=re.MULTILINE)  # [Speaker Name]
    text = re.sub(r'^\s*\(.*?\)\s*', '', text, flags=re.MULTILINE)  # (sound effects)
    text = re.sub(r'<v\s+[^>]+>', '', text)  # <v Speaker Name>
    
    # Remove HTML-style tags and formatting
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&\w+;', '', text)  # HTML entities
    
    # Remove any decimal numbers that might be part of formatting
    text = re.sub(r'\.\d{3}\s*', '', text)
    
    # Clean up whitespace
    text = re.sub(r'\s*\n\s*\n\s*', '\n', text)  # Multiple newlines to single
    text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
    text = re.sub(r'^\s+|\s+$', '', text, flags=re.MULTILINE)  # Trim lines
    
    # Fix common punctuation issues
    text = re.sub(r'\s+([.,!?])', r'\1', text)  # Remove space before punctuation
    text = re.sub(r'([.,!?])\s+', r'\1 ', text)  # Ensure single space after punctuation
    
    # Final cleanup
    text = text.strip()
    
    # Ensure sentences are properly spaced
    text = re.sub(r'(?<=[.!?])\s*(?=[A-Z])', ' ', text)
    
    return text

def save_json_to_file(data, channel_id):
    if not os.path.exists('reports'):
        os.makedirs('reports')
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reports/channel_data_{timestamp}_{channel_id}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"Channel data saved to {filename}")
    return filename

def fetch_channel_data(channel_id):
    try:
        channel_response = youtube.channels().list(
            part="snippet,statistics,brandingSettings",
            id=channel_id
        ).execute()

        if 'items' in channel_response:
            channel_info = channel_response['items'][0]
            channel_data = {
                'channel_id': channel_id,
                'title': channel_info['snippet']['title'],
                'description': channel_info['snippet']['description'],
                'subscriber_count': channel_info['statistics']['subscriberCount'],
                'total_view_count': channel_info['statistics']['viewCount'],
                'total_video_count': channel_info['statistics']['videoCount'],
                'avatar_url': channel_info['snippet']['thumbnails']['default']['url'],
                'banner_url': channel_info['brandingSettings']['image'].get('bannerExternalUrl', ''),
                'trailer_video_id': channel_info['brandingSettings']['channel'].get('unsubscribedTrailer', ''),
                'videos': []
            }
            
            # Get info for the most recent videos
            channel_data['videos'] = get_channel_videos(channel_id, MAX_VIDEOS)
            
            # Sort videos by date (most recent first) and get subtitles for only the most recent ones
            channel_data['videos'].sort(key=lambda x: x['date_published'], reverse=True)
            
            for video in channel_data['videos'][:MAX_VIDEOS_FOR_SUBTITLES]:
                subtitles = get_video_subtitles(video['youtube_video_id'])
                if subtitles:
                    video['subtitles'] = subtitles
                    print(f"Retrieved subtitles for video: {video['title']}")
                else:
                    print(f"No subtitles available for video: {video['title']}")

            return channel_data
        else:
            return None

    except Exception as e:
        print(f"An error occurred while fetching channel data: {e}")
        return None


def test_cookies(cookie_file):
    """Utility function to test cookie validity and provide detailed feedback."""
    logging.info(f"Testing cookies from: {cookie_file}")
    
    # First check file exists and is readable
    if not os.path.exists(cookie_file):
        logging.error("Cookie file does not exist")
        return False
        
    try:
        # Read and check cookie content
        with open(cookie_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            logging.info(f"Cookie file contains {len(lines)} lines")
            
            # Check for essential cookies
            youtube_cookies = []
            for line in lines:
                if '.youtube.com' in line and 'TRUE' in line and not line.startswith('#'):
                    parts = line.split('\t')
                    if len(parts) >= 6:
                        cookie_name = parts[5] if len(parts) > 5 else 'unknown'
                        youtube_cookies.append(cookie_name)
                        
            logging.info(f"Found YouTube cookies: {', '.join(youtube_cookies)}")
            
        # Test with yt-dlp
        test_opts = {
            'quiet': True,
            'no_warnings': True,
            'cookiefile': cookie_file,
            'extract_flat': True,
            'skip_download': True,
            'no_write_download_archive': True,
            'no_cache_dir': True,
        }
        
        with yt_dlp.YoutubeDL(test_opts) as ydl:
            logging.info("Attempting to fetch video info with cookies...")
            try:
                # Try to extract just the title
                result = ydl.extract_info(
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    download=False,
                    process=False
                )
                if result and 'title' in result:
                    logging.info(f"Successfully retrieved video title: {result.get('title')}")
                    return True
                else:
                    logging.error("Failed to extract video info")
                    return False
            except Exception as e:
                logging.error(f"Error during yt-dlp test: {str(e)}")
                return False
                
    except Exception as e:
        logging.error(f"Error testing cookies: {str(e)}")
        return False

# Add this to your code and call it when needed
'''if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    cookie_file = "youtube_cookies.txt"  # Adjust path as needed
    test_cookies(cookie_file)'''

# GARBAGE

'''def create_temp_cookie_file():
    """Create a temporary copy of the cookie file with appropriate permissions."""
    if not os.path.exists(COOKIE_FILE):
        logging.error(f"Original cookie file {COOKIE_FILE} not found")
        return None, None
        
    try:
        # Create a temporary directory to store our cookie file
        temp_dir = tempfile.mkdtemp(prefix='yt_cookies_')
        temp_cookie_file = os.path.join(temp_dir, 'cookies.txt')
        
        # Copy the original cookie file to the temporary location
        shutil.copy2(COOKIE_FILE, temp_cookie_file)
        
        # First make the file read/write for owner only
        os.chmod(temp_cookie_file, stat.S_IRUSR | stat.S_IWUSR)
        
        # Create a backup of the original cookie file
        cookie_backup = f"{COOKIE_FILE}.backup"
        if not os.path.exists(cookie_backup):
            shutil.copy2(COOKIE_FILE, cookie_backup)
            logging.info(f"Created backup of original cookie file: {cookie_backup}")
        
        # Make both the original and temporary cookie files read-only
        os.chmod(COOKIE_FILE, stat.S_IRUSR)
        os.chmod(temp_cookie_file, stat.S_IRUSR)
        
        logging.info(f"Created temporary cookie file: {temp_cookie_file}")
        return temp_cookie_file, temp_dir
        
    except Exception as e:
        logging.error(f"Error creating temporary cookie file: {str(e)}")
        if 'temp_dir' in locals() and temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return None, None

def cleanup_temp_cookie_file(temp_file, temp_dir):
    """Clean up the temporary cookie file and its directory."""
    try:
        if temp_file and os.path.exists(temp_file):
            # Make writable before deletion
            os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)
            os.remove(temp_file)
            logging.info(f"Removed temporary cookie file: {temp_file}")
        
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info(f"Removed temporary directory: {temp_dir}")
            
    except Exception as e:
        logging.error(f"Error in cleanup_temp_cookie_file: {str(e)}")'''