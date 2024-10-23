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

# Use configuration values
API_KEY = Config.YOUTUBE_API_KEY # os.environ.get('YOUTUBE_API_KEY')
OPENAI_API_KEY = Config.OPENAI_API_KEY # os.environ.get('OPENAI_API_KEY')
MAX_VIDEOS = Config.MAX_VIDEOS_TO_FETCH # app_config['max_videos_to_fetch']
MAX_VIDEOS_FOR_SUBTITLES = Config.MAX_VIDEOS_FOR_SUBTITLES # app_config['max_videos_for_subtitles']
OPENAI_MODEL = Config.OPENAI_MODEL # app_config['openai_model']
MAX_TOKENS = Config.MAX_TOKENS # app_config['max_tokens']

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize YouTube API client
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

def extract_channel_id(url):
    parsed_url = urlparse(url)
    
    if 'youtube.com' in parsed_url.netloc or 'youtu.be' in parsed_url.netloc:
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
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
                print(f"Error fetching channel ID for @{username}: {e}")
                return None
        elif path.startswith('/channel/'):
            return path.split('/')[2]
        elif 'v' in query:
            video_id = query['v'][0]
            try:
                video_response = youtube.videos().list(
                    part="snippet",
                    id=video_id
                ).execute()
                if 'items' in video_response:
                    return video_response['items'][0]['snippet']['channelId']
            except Exception as e:
                print(f"Error fetching channel ID for video {video_id}: {e}")
                return None
        elif path.startswith('/c/') or path.startswith('/user/'):
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
                print(f"Error fetching channel ID for {custom_name}: {e}")
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

def get_yt_dlp_opts():
    return {
        'nocheckcertificate': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'quiet': True,
        'no_color': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'cookiefile': 'youtube_cookies.txt',
        'no_cache_dir': True
    }

def get_video_subtitles(video_id):
    """
    Fetch the subtitle file for a given video ID using yt-dlp.
    Returns only the spoken text content without formatting, timestamps, or metadata.
    Returns None if no subtitles are available.
    """
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    ydl_opts = get_yt_dlp_opts()
    ydl_opts.update({
        'skip_download': True,
        'writesubtitles': True,
        'writeautomaticsub': True,
        'subtitleslangs': ['en', 'en-US'],
        'subtitlesformat': 'vtt',
        'outtmpl': '%(id)s.%(ext)s'
    })
    
    logging.info(f"Attempting to fetch subtitles for video: {video_id}")
    logging.debug(f"yt-dlp options: {ydl_opts}")
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
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
                subtitle_filename = f"{video_id}{subtitle_ext}"
                logging.info(f"Looking for subtitle file: {subtitle_filename}")
                
                if os.path.exists(subtitle_filename):
                    logging.info(f"Subtitle file found. Reading content...")
                    with open(subtitle_filename, 'r', encoding='utf-8') as f:
                        subtitle_content = f.read()
                    
                    # Clean up the subtitle content
                    cleaned_text = clean_subtitle_text(subtitle_content)
                    
                    logging.info("Cleaning up downloaded file...")
                    os.remove(subtitle_filename)
                    
                    logging.info("Subtitles successfully extracted and processed.")
                    return cleaned_text
            
            logging.error(f"No subtitle file found for any of the expected formats.")
        except Exception as e:
            logging.exception(f"An error occurred while fetching subtitles for video {video_id}: {str(e)}")
    
    return None

def clean_subtitle_text(subtitle_content):
    """
    Clean subtitle content to extract only the spoken text.
    Removes all formatting, timestamps, and metadata.
    """
    # Remove WEBVTT header and metadata
    text = re.sub(r'WEBVTT\n.*?\n\n', '', subtitle_content, flags=re.DOTALL)
    
    # Remove timestamps (including arrow and newlines)
    text = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\n', '', text)
    
    # Remove shorter timestamp formats
    text = re.sub(r'\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}\.\d{3}\n', '', text)
    
    # Remove line numbers
    text = re.sub(r'^\d+\n', '', text, flags=re.MULTILINE)
    
    # Remove speaker labels (text in parentheses or brackets at start of lines)
    text = re.sub(r'^\s*[\[\(].*?[\]\)]\s*', '', text, flags=re.MULTILINE)
    
    # Remove HTML-style tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Remove multiple newlines and replace with space
    text = re.sub(r'\n+', ' ', text)
    
    # Remove any remaining timing marks (sometimes found in different formats)
    text = re.sub(r'\d{2}:\d{2}(?::\d{2})?\s*', '', text)
    
    # Clean up any artifacts from removal process
    text = re.sub(r'\s+[,.]', '.', text)  # Fix spacing around punctuation
    text = re.sub(r'\s+', ' ', text)      # Remove any double spaces
    text = text.strip()                    # Remove leading/trailing whitespace
    
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
    