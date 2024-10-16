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

## DEPRECATED CONFIG SYSTEM
'''
def load_config():
    try:
        with open('config.json', 'r') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        print("Configuration file 'config.json' not found. Please create it and add your settings.")
        exit(1)
    except json.JSONDecodeError:
        print("Error parsing 'config.json'. Please make sure it's valid JSON.")
        exit(1)

# Load configuration
app_config = load_config()
'''

# Use configuration values
API_KEY = Config.YOUTUBE_API_KEY # os.environ.get('YOUTUBE_API_KEY')
OPENAI_API_KEY = Config.OPENAI_API_KEY # os.environ.get('OPENAI_API_KEY')
MAX_VIDEOS = Config.MAX_VIDEOS_TO_FETCH # app_config['max_videos_to_fetch']
MAX_VIDEOS_FOR_SUBTITLES = Config.MAX_VIDEOS_FOR_SUBTITLES # app_config['max_videos_for_subtitles']
OPENAI_MODEL = Config.OPENAI_MODEL # app_config['openai_model']
MAX_TOKENS = Config.MAX_TOKENS # app_config['max_tokens']

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
            print(f"Retrieved subtitles for video: {video['snippet']['title']}")
        else:
            print(f"No subtitles available for video: {video['snippet']['title']}")

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

def get_video_subtitles(video_id):
    """
    Fetch the subtitle file for a given video ID without authentication.
    Returns the subtitles as a string with only the text content, if found, None otherwise.
    """
    try:
        # First, we need to get the available caption tracks
        url = f'https://youtube.com/watch?v={video_id}'
        response = requests.get(url)
        response.raise_for_status()
        
        # Extract the caption track URL from the video page
        captions_regex = r'"captions":.*?"captionTracks":(\[.*?\])'
        captions_match = re.search(captions_regex, response.text)
        
        if not captions_match:
            print("DEBUG: No caption tracks found in the video page")
            return None
        
        captions_data = json.loads(captions_match.group(1))
        
        # Find the English auto-generated captions
        subtitle_url = None
        for caption in captions_data:
            if caption.get('vssId', '').endswith('.en'):
                subtitle_url = caption['baseUrl']
                break
        
        if not subtitle_url:
            print("DEBUG: No English auto-generated captions found")
            return None
        
        # Fetch the actual subtitle content
        subtitle_response = requests.get(subtitle_url)
        subtitle_response.raise_for_status()

       # Parse the XML content
        try:
            root = ET.fromstring(subtitle_response.text)
        except ET.ParseError as e:
            print(f"DEBUG: Error parsing XML: {e}")
            return None
        
        # Extract only the text content of the subtitles
        subtitles = []
        for text in root.findall('.//text'):
            content = text.text
            if content:
                subtitles.append(content)
        
        # Join all subtitle texts into a single string
        return ' '.join(subtitles)

    except requests.RequestException as e:
        print(f"DEBUG: An error occurred while fetching subtitles: {e}")
        return None

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