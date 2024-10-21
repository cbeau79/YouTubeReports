import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import re
import json
import xml.etree.ElementTree as ET
import logging
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def sanitize_filename(filename):
    """
    Remove or replace characters that are unsafe for filenames.
    """
    # Replace slashes with underscores
    filename = filename.replace('/', '_').replace('\\', '_')
    # Remove characters that are generally unsafe for filenames
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def requests_retry_session(
    retries=3,
    backoff_factor=0.3,
    status_forcelist=(500, 502, 504),
    session=None,
):
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def get_video_subtitles(video_id):
    logging.info(f"Attempting to fetch subtitles for video ID: {video_id}")
    try:
        session = requests_retry_session()
        
        # Set multiple User-Agent strings to try
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15'
        ]
        
        '''headers = {
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }'''

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # First, make a request to the YouTube homepage
        session.get('https://www.youtube.com/', headers=headers)
        
        url = f'https://youtube.com/watch?v={video_id}'
        
        for user_agent in user_agents:
            headers['User-Agent'] = user_agent
            print(headers)
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            logging.debug(f"Response received with User-Agent: {user_agent}")
            
            # Sanitize the user agent string for use in filename
            safe_user_agent = sanitize_filename(user_agent)[:30]  # Limit length to 30 characters
            
            # Write the full HTML response to a file
            filename = f'youtube_response_{video_id}_{safe_user_agent}.html'
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logging.info(f"Wrote response to file: {filename}")
            
            # Extract the caption track URL from the video page
            captions_regex = r'"captions":.*?"captionTracks":(\[.*?\])'
            captions_match = re.search(captions_regex, response.text)
            
            if captions_match:
                captions_data = json.loads(captions_match.group(1))
                logging.debug(f"Caption data extracted: {captions_data}")
                
                # Find the English auto-generated captions
                subtitle_url = next((caption['baseUrl'] for caption in captions_data if caption.get('vssId', '').endswith('.en')), None)
                
                if subtitle_url:
                    logging.info(f"Fetching subtitle content from {subtitle_url}")
                    subtitle_response = session.get(subtitle_url, headers=headers, timeout=10)
                    subtitle_response.raise_for_status()

                    # Write the subtitle XML to a file
                    subtitle_filename = f'youtube_subtitles_{video_id}.xml'
                    with open(subtitle_filename, 'w', encoding='utf-8') as f:
                        f.write(subtitle_response.text)
                    logging.info(f"Wrote subtitles to file: {subtitle_filename}")

                    # Parse the XML content
                    try:
                        root = ET.fromstring(subtitle_response.text)
                        subtitles = ' '.join(text.text for text in root.findall('.//text') if text.text)
                        logging.info(f"Successfully extracted subtitles for {video_id}")
                        return subtitles
                    except ET.ParseError as e:
                        logging.error(f"Error parsing XML for {video_id}: {e}")
                
            logging.warning(f"No suitable captions found with User-Agent: {user_agent}")
        
        logging.error("Failed to find captions with all User-Agents")
        return None

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

print("Check the current directory for HTML and XML files with the response content.")
print(f"Current working directory: {os.getcwd()}")
