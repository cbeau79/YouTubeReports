import requests
import re
import json
import xml.etree.ElementTree as ET
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def get_video_subtitles(video_id):
    """
    Fetch the subtitle file for a given video ID without authentication.
    Returns the subtitles as a string with only the text content, if found, None otherwise.
    """
    logging.info(f"Attempting to fetch subtitles for video ID: {video_id}")
    try:
        # Set a more browser-like User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        url = f'https://youtube.com/watch?v={video_id}'
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        logging.debug(f"Successfully fetched video page for {video_id}")
        
        # Extract the caption track URL from the video page
        captions_regex = r'"captions":.*?"captionTracks":(\[.*?\])'
        captions_match = re.search(captions_regex, response.text)
        
        if not captions_match:
            logging.warning(f"No caption tracks found in the video page for {video_id}")
            return None
        
        captions_data = json.loads(captions_match.group(1))
        logging.debug(f"Caption data extracted: {captions_data}")
        
        # Find the English auto-generated captions
        subtitle_url = None
        for caption in captions_data:
            if caption.get('vssId', '').endswith('.en'):
                subtitle_url = caption['baseUrl']
                break
        
        if not subtitle_url:
            logging.warning(f"No English auto-generated captions found for {video_id}")
            return None
        
        logging.info(f"Fetching subtitle content from {subtitle_url}")
        
        # Fetch the actual subtitle content
        subtitle_response = requests.get(subtitle_url, headers=headers, timeout=10)
        subtitle_response.raise_for_status()

        # Parse the XML content
        try:
            root = ET.fromstring(subtitle_response.text)
        except ET.ParseError as e:
            logging.error(f"Error parsing XML for {video_id}: {e}")
            return None
        
        # Extract only the text content of the subtitles
        subtitles = []
        for text in root.findall('.//text'):
            content = text.text
            if content:
                subtitles.append(content)
        
        # Join all subtitle texts into a single string
        subtitle_text = ' '.join(subtitles)
        logging.info(f"Successfully extracted subtitles for {video_id}")
        return subtitle_text

    except requests.RequestException as e:
        logging.error(f"Request error while fetching subtitles for {video_id}: {e}")
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error for {video_id}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while fetching subtitles for {video_id}: {e}")
    
    return None

# Test the function with a known video ID
video_id = "dQw4w9WgXcQ"  # This is the ID for Rick Astley's "Never Gonna Give You Up"
subtitles = get_video_subtitles(video_id)

if subtitles:
    print("Subtitles fetched successfully:")
    print(subtitles[:500])  # Print the first 500 characters of the subtitles
else:
    print("Failed to fetch subtitles.")
