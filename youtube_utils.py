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
config = load_config()

# Use configuration values
API_KEY = config['youtube_api_key']
OPENAI_API_KEY = config['openai_api_key']
MAX_VIDEOS = config['max_videos_to_fetch']
MAX_VIDEOS_FOR_SUBTITLES = config['max_videos_for_subtitles']
OPENAI_MODEL = config['openai_model']
MAX_TOKENS = config['max_tokens']

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

def get_video_data(video_id):
    output = []

    video_response = youtube.videos().list(
        part="snippet,contentDetails,statistics",
        id=video_id
    ).execute()

    # print(json.dumps(video_response, indent=2))

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

        output.append({
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
        })

        print(json.dumps(output, indent=2))
    
    return output


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
            part="snippet,statistics",
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
    

# --------------------------------------------------------
# - I DON'T BELIEVE THESE FUNCTIONS ARE BEING USED ANYMORE
# --------------------------------------------------------

def parse_json_string(input_string):
    print("\n---\n")
    print(input_string)
    print("\n---\n")
    
    # Unescape the string
    clean_string = input_string.encode().decode('unicode_escape')
    print(clean_string)
    print("\n---\n")
    
    # Strip the outer quotation marks
    clean_string = clean_string.strip('"')
    print(clean_string)
    print("\n---\n")

    # Strip the tripple backticks
    clean_string = clean_string.strip('```')
    print(clean_string)
    print("\n---\n")

    # Remove the json at the start, if it's there
    if clean_string.startswith('json'):
        clean_string = clean_string[4:]
    print(clean_string)
    print("\n---\n")

    try:
        # Parse the string as JSON
        json_data = json.loads(clean_string)
        return json_data
    except json.JSONDecodeError as e:
        print(f"youtube_utils.py: Error parsing JSON string: {e}")
        return None