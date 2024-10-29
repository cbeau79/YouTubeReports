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
from cookie_manager import CookieValidator

# Use configuration values
API_KEY = Config.YOUTUBE_API_KEY # os.environ.get('YOUTUBE_API_KEY')
OPENAI_API_KEY = Config.OPENAI_API_KEY # os.environ.get('OPENAI_API_KEY')
MAX_VIDEOS = Config.MAX_VIDEOS_TO_FETCH # app_config['max_videos_to_fetch']
MAX_VIDEOS_FOR_SUBTITLES = Config.MAX_VIDEOS_FOR_SUBTITLES # app_config['max_videos_for_subtitles']
OPENAI_MODEL = Config.OPENAI_MODEL # app_config['openai_model']
MAX_TOKENS = Config.MAX_TOKENS # app_config['max_tokens']
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth/ytc.txt")

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

# ---
# SUBTITLE FUNCTIONS
# ---

def create_temp_cookie_file():
    """Create a temporary copy of the cookie file with appropriate permissions."""
    if not os.path.exists(COOKIE_FILE):
        logging.error(f"Original cookie file {COOKIE_FILE} not found")
        return None
        
    try:
        # Create a temporary file
        temp_cookie_file = os.path.join(tempfile.gettempdir(), f"yt_cookies_{os.getpid()}.txt")
        
        # Copy the original cookie file to the temporary location
        shutil.copy2(COOKIE_FILE, temp_cookie_file)

        # DELETE ME
        shutil.copy2(temp_cookie_file, 'temp_before.txt')
        
        # Set appropriate permissions on the temporary file
        #os.chmod(temp_cookie_file, stat.S_IRUSR | stat.S_IWUSR)  # Read and write for owner
        os.chmod(temp_cookie_file, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)  # Read-only for everyone
        
        logging.info(f"Created temporary cookie file: {temp_cookie_file}")
        return temp_cookie_file
        
    except Exception as e:
        logging.error(f"Error creating temporary cookie file: {str(e)}")
        return None

def cleanup_temp_cookie_file(temp_file):
    """Clean up the temporary cookie file."""
    if temp_file and os.path.exists(temp_file):
        try:
            # Ensure the file is writable before attempting to delete
            try:
                os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)
            except Exception as e:
                logging.warning(f"Could not modify permissions for cleanup: {str(e)}")
            
            # DELETE ME
            shutil.copy2(temp_file, 'temp_after.txt')
                
            os.remove(temp_file)
            logging.info(f"Removed temporary cookie file: {temp_file}")
        except Exception as e:
            logging.warning(f"Error removing temporary cookie file: {str(e)}")

def get_video_subtitles(video_id):
    """
    Fetch the subtitle file for a given video ID using yt-dlp.
    Returns only the spoken text content without formatting, timestamps, or metadata.
    Returns None if subtitles are not available.
    """
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    temp_cookie_file = None
    subtitles_text = None

    try:
        temp_cookie_file = create_temp_cookie_file()
        
        if not temp_cookie_file:
            logging.error("Failed to create temporary cookie file")
            return None
        
        # Create yt-dlp options
        ydl_opts = {
            'nocheckcertificate': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'quiet': True,
            'no_color': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'cookiefile': temp_cookie_file,
            'no_cache_dir': True,
            'no_overwrites': True,
            'no_cookies': True
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts.update({
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US'],
                'subtitlesformat': 'vtt',
                'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s')
            })
            
            logging.info(f"Attempting to fetch subtitles for video: {video_id}")
            logging.debug(f"yt-dlp options: {ydl_opts}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logging.info("Extracting video info...")
                info = ydl.extract_info(video_url, download=False)
                logging.debug(f"Video info extracted: {info.keys()}")
                
                subtitle_formats = ['.en.vtt', '.en-US.vtt', '.en.ttml', '.en-US.ttml', '.en.srv3', '.en-US.srv3']
                
                # Check for and download subtitles
                if 'subtitles' in info and ('en' in info['subtitles'] or 'en-US' in info['subtitles']):
                    logging.info("Manual English subtitles found. Downloading...")
                    ydl.download([video_url])
                elif 'automatic_captions' in info and ('en' in info['automatic_captions'] or 'en-US' in info['automatic_captions']):
                    logging.info("Automatic English captions found. Downloading...")
                    ydl.download([video_url])
                else:
                    logging.warning(f"No English subtitles or captions available for video: {video_id}")
                    return None

                # Process the subtitle file
                for subtitle_ext in subtitle_formats:
                    subtitle_filename = os.path.join(temp_dir, f"{video_id}{subtitle_ext}")
                    logging.info(f"Looking for subtitle file: {subtitle_filename}")
                    
                    if os.path.exists(subtitle_filename):
                        logging.info(f"Subtitle file found. Reading content...")
                        with open(subtitle_filename, 'r', encoding='utf-8') as f:
                            subtitle_content = f.read()
                        
                        # Clean up the subtitle content
                        subtitles_text = clean_subtitle_text(subtitle_content)
                        logging.info("Subtitles successfully extracted and processed.")
                        break  # Exit loop once we have successful extraction

    except Exception as e:
        logging.error(f"Error in subtitle extraction: {str(e)}")
        # Don't return None here - we might have subtitles despite the error
        
    finally:
        # Try to clean up the temporary cookie file, but don't let cleanup failures affect the result
        if temp_cookie_file:
            try:
                cleanup_temp_cookie_file(temp_cookie_file)
            except Exception as e:
                logging.warning(f"Non-critical error during cleanup: {str(e)}")
                # Continue anyway - cleanup failure shouldn't invalidate successful subtitle extraction

    return subtitles_text  # Return whatever we got, even if cleanup failed

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
    
''' *** MISGUIDED IDEAS *** '''

'''def get_yt_dlp_opts():
    """Get yt-dlp options with cookie file configuration."""
    temp_cookie_file = create_temp_cookie_file()
    if not temp_cookie_file:
        return None
    
    return {
        'nocheckcertificate': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'quiet': True,
        'no_color': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'cookiefile': temp_cookie_file,
        'no_cache_dir': True
    }

def get_video_subtitles(video_id):
    """
    Fetch the subtitle file for a given video ID using yt-dlp.
    Returns only the spoken text content without formatting, timestamps, or metadata.
    Returns None if no subtitles are available.
    """
    video_url = f'https://www.youtube.com/watch?v={video_id}'

    temp_cookie_file = create_temp_cookie_file()
    
    if not temp_cookie_file:
        logging.error("Failed to create temporary cookie file")
        return None
    
    try:
        # Validate cookies before proceeding
        # cookie_validator = CookieValidator(COOKIE_FILE)
        # is_valid, message = cookie_validator.check_status()
        
        if not is_valid:
            logging.error(f"Cookie validation failed: {message}")
            # You could implement some notification system here
            # For now, just log it prominently
            logging.critical("ATTENTION: YouTube cookies need to be refreshed!")
            return None

        # Create yt-dlp options
        ydl_opts = {
            'nocheckcertificate': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'quiet': True,
            'no_color': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'cookiefile': temp_cookie_file,
            'no_cache_dir': True,
            'no_overwrites': True,
            'no_cookies': True
        }
        
        # DELETE ME
        shutil.copy2(temp_cookie_file, 'temp_during.txt')

        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts.update({
                'skip_download': True,
                'writesubtitles': True,
                'writeautomaticsub': True,
                'subtitleslangs': ['en', 'en-US'],
                'subtitlesformat': 'vtt',
                'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s')
            })
            
            logging.info(f"Attempting to fetch subtitles for video: {video_id}")
            logging.debug(f"yt-dlp options: {ydl_opts}")
            
            subtitles_text = None  # Variable to store successful subtitle extraction
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logging.info("Extracting video info...")
                info = ydl.extract_info(video_url, download=False)
                logging.debug(f"Video info extracted: {info.keys()}")
                
                subtitle_formats = ['.en.vtt', '.en-US.vtt', '.en.ttml', '.en-US.ttml', '.en.srv3', '.en-US.srv3']
                
                # Check for and download subtitles
                if 'subtitles' in info and ('en' in info['subtitles'] or 'en-US' in info['subtitles']):
                    logging.info("Manual English subtitles found. Downloading...")
                    ydl.download([video_url])
                elif 'automatic_captions' in info and ('en' in info['automatic_captions'] or 'en-US' in info['automatic_captions']):
                    logging.info("Automatic English captions found. Downloading...")
                    ydl.download([video_url])
                else:
                    logging.warning(f"No English subtitles or captions available for video: {video_id}")
                    return None
                
                # DELETE ME
                shutil.copy2(temp_cookie_file, 'temp_during_2.txt')

                # Process the subtitle file
                for subtitle_ext in subtitle_formats:
                    subtitle_filename = os.path.join(temp_dir, f"{video_id}{subtitle_ext}")
                    logging.info(f"Looking for subtitle file: {subtitle_filename}")
                    
                    if os.path.exists(subtitle_filename):
                        logging.info(f"Subtitle file found. Reading content...")
                        with open(subtitle_filename, 'r', encoding='utf-8') as f:
                            subtitle_content = f.read()
                        
                        # Clean up the subtitle content
                        subtitles_text = clean_subtitle_text(subtitle_content)
                        logging.info("Subtitles successfully extracted and processed.")
                        break  # Exit loop once we have successful extraction
                
                return subtitles_text  # Return the subtitles if we found them
                
    except Exception as e:
        logging.error(f"Error in subtitle extraction: {str(e)}")
        return None
        
    finally:
        # Always try to clean up the temporary cookie file
        try:
            cleanup_temp_cookie_file(temp_cookie_file)
        except Exception as e:
            logging.warning(f"Error during cleanup: {str(e)}")'''