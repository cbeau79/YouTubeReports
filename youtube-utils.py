# youtube_utils.py
import os
import json
import googleapiclient.discovery
from urllib.parse import urlparse, parse_qs
import isodate
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI

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
OPENAI_MODEL = config['openai_model']
MAX_TOKENS = config['max_tokens']

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize YouTube API client
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

def extract_channel_id(url):
    parsed_url = urlparse(url)
    
    if 'youtube.com' in parsed_url.netloc:
        query = parse_qs(parsed_url.query)
        path = parsed_url.path
        
        if path.startswith('/channel/'):
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
            except:
                return None
        elif 'c' in query:
            return query['c'][0]
        elif path.startswith('/c/') or path.startswith('/user/'):
            custom_name = path.split('/')[2]
            try:
                channel_response = youtube.search().list(
                    part="snippet",
                    q=custom_name,
                    type="channel"
                ).execute()
                if 'items' in channel_response:
                    return channel_response['items'][0]['snippet']['channelId']
            except:
                return None
    
    return None

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
                    'length': int(duration_seconds),
                    'date_published': video['snippet']['publishedAt'],
                    'tags': video['snippet'].get('tags', []),
                    'video_id': video['id'],
                    'views': int(video['statistics'].get('viewCount', 0)),
                    'category_id': video['snippet'].get('categoryId', 'Unknown'),
                    'like_count': int(video['statistics'].get('likeCount', 0)),
                    'comment_count': int(video['statistics'].get('commentCount', 0)),
                    'thumbnail_url': video['snippet']['thumbnails']['default']['url']
                })

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return videos[:max_results]

def get_video_subtitles(video_id):
    try:
        url = f'https://youtube.com/watch?v={video_id}'
        response = requests.get(url)
        response.raise_for_status()
        
        captions_regex = r'"captions":.*?"captionTracks":(\[.*?\])'
        captions_match = re.search(captions_regex, response.text)
        
        if not captions_match:
            return None
        
        captions_data = json.loads(captions_match.group(1))
        
        subtitle_url = None
        for caption in captions_data:
            if caption.get('vssId', '').endswith('.en'):
                subtitle_url = caption['baseUrl']
                break
        
        if not subtitle_url:
            return None
        
        subtitle_response = requests.get(subtitle_url)
        subtitle_response.raise_for_status()
        
        root = ET.fromstring(subtitle_response.text)
        
        subtitles = []
        for text in root.findall('.//text'):
            content = text.text
            if content:
                subtitles.append(content)
        
        return ' '.join(subtitles)

    except Exception as e:
        print(f"An error occurred while fetching subtitles: {e}")
        return None

def generate_channel_report(channel_data):
    full_data_json = json.dumps(channel_data, indent=2)

    prompt = f"""
    You are a YouTube content consultant. Analyze the following complete YouTube channel data and provide a comprehensive report. The data is provided in JSON format:

    {full_data_json}

    Analyze this data and present the key findings in the following format: 
    1. Executive Summary
        1. Content summary (1 paragraph)
        2. Channel hosts and personalities (1 paragraph - if you don't know anything about the hosts and personalities, it's ok to say so)
        3. Channel prominence and competitive landscape (1 paragraph)
    2. Key Metrics (1-2 sentences of context and rationale for each): 
        1. Average views per video 
        2. Top-performing video category 
        3. Average number of videos published per week 
    3. Trends: 
        1. List 3 notable trends, each with a brief explanation
    4. Writing style:
        1. Using the subtitle data only, do an analysis of the writing style of the videos. It should be two paragraphs long.
    5. Recommendations: 
        1. Provide 3 data-driven recommendations, each with a brief rationale

    Provide your analysis in a clear, structured format. Use specific data points to support your insights and recommendations. If you identify any limitations in the data provided, please mention them. Do not rush to come up with an answer, take your time.
    """

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a YouTube content consultant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=MAX_TOKENS
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"An error occurred while generating the report: {e}")
        return ""

def fetch_channel_data(channel_id):
    try:
        channel_response = youtube.channels().list(
            part="snippet,statistics",
            id=channel_id
        ).execute()

        if 'items' in channel_response:
            channel_info = channel_response['items'][0]
            channel_data = {
                'title': channel_info['snippet']['title'],
                'description': channel_info['snippet']['description'],
                'subscriber_count': channel_info['statistics']['subscriberCount'],
                'total_view_count': channel_info['statistics']['viewCount'],
                'videos': []
            }
            
            channel_data['videos'] = get_channel_videos(channel_id, MAX_VIDEOS)
            
            for video in channel_data['videos']:
                subtitles = get_video_subtitles(video['video_id'])
                if subtitles:
                    video['subtitles'] = subtitles

            return channel_data
        else:
            return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None
