# app.py
from app import Flask, render_template, request, jsonify
from yt_reports import generate_channel_report, load_config, get_channel_videos, get_video_subtitles
import googleapiclient.discovery
import re
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

# Load configuration
config = load_config()
API_KEY = config['youtube_api_key']
OPENAI_API_KEY = config['openai_api_key']
MAX_VIDEOS = config['max_videos_to_fetch']

# Initialize YouTube API client
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=API_KEY)

# Index Route
@app.route('/')
def index():
    return render_template('index.html')

# Analyze Route
@app.route('/analyze', methods=['POST'])
def analyze():
    channel_url = request.form['channel_url']
    
    # Extract channel ID from URL
    channel_id = extract_channel_id(channel_url)
    
    if not channel_id:
        return jsonify({'error': 'Invalid YouTube channel URL'})
    
    # Fetch channel data
    channel_data = fetch_channel_data(channel_id)
    
    if not channel_data:
        return jsonify({'error': 'Unable to fetch channel data'})
    
    # Generate report
    report = generate_channel_report(channel_data)
    
    return jsonify({'report': report})

def extract_channel_id(url):
    # Function to extract channel ID from various YouTube URL formats
    parsed_url = urlparse(url)
    
    # Check for channel ID in query string (e.g., youtube.com/channel/UC...)
    if 'youtube.com' in parsed_url.netloc:
        query = parse_qs(parsed_url.query)
        path = parsed_url.path
        
        if path.startswith('/channel/'):
            return path.split('/')[2]
        elif 'v' in query:
            # If it's a video URL, we need to make an API call to get the channel ID
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
            # Custom URL format
            return query['c'][0]
        elif path.startswith('/c/') or path.startswith('/user/'):
            # Custom URL or username format
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
    
    # If we can't determine the channel ID, return None
    return None

def fetch_channel_data(channel_id):
    try:
        # Get channel info
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
            
            # Get info for the most recent videos
            channel_data['videos'] = get_channel_videos(channel_id, MAX_VIDEOS)
            
            # Get subtitles for the videos
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

if __name__ == '__main__':
    app.run(debug=True)
