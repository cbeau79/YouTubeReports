# test_subtitles.py
import sys
import logging
import yt_dlp
import os
import re
import json
import requests

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
temp_dir = 'tmp/'
video_url = f'https://www.youtube.com/watch?v={sys.argv[1]}'

def get_video_subtitles(video_id):
    """
    Fetch the subtitle file for a given video ID using yt-dlp.
    Returns only the spoken text content without formatting, timestamps, or metadata.
    Returns None if subtitles are not available.
    """
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    temp_cookie_file = None
    subtitles_text = None
    temp_dir = 'tmp/'

    try:
        temp_cookie_file = create_temp_cookie_file()
        
        if not temp_cookie_file:
            logging.error("Failed to create temporary cookie file")
            return None
        
        # Create yt-dlp options with format specification
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
            'no_cookies': True,
            'format': 'best', 
            'extract_flat': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'en-US'],
            'subtitlesformat': 'vtt',
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s')
        }

        ydl_opts = {
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsubs': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            # 'subtitleslangs': ['en', 'en-US'],
            # 'subtitlesformat': 'vtt',
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s')
        }
        
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

    with open('subtitles.txt', 'w') as file:
        file.write(subtitles_text)

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

def extract_transcript_text(transcript_content: str) -> str:
    """
    Extracts plain text from an SRT-like transcript format, removing all XML tags
    and timing information.

    Args:
        transcript_content (str): The raw transcript content containing XML tags and timing info

    Returns:
        str: Clean text with just the spoken content, with proper spacing between segments

    Example:
        >>> content = '''<transcript>
        ... <text start="1.0" dur="2.0">Hello world</text>
        ... <text start="3.0" dur="2.0">How are you</text>
        ... </transcript>'''
        >>> print(extract_transcript_text(content))
        'Hello world How are you'
    """

    try:
        # Strip out all XML tags except text content
        text_pattern = r'<text[^>]*>(.*?)</text>'
        text_segments = re.findall(text_pattern, transcript_content)

        if not text_segments:
            raise ValueError("No valid text segments found in transcript")

        # Join segments with a space and clean up any extra whitespace
        clean_text = ' '.join(text_segments)
        
        # Clean up whitespace issues
        clean_text = re.sub(r'\s+', ' ', clean_text)  # Multiple spaces to single
        clean_text = re.sub(r'^\s+|\s+$', '', clean_text)  # Trim ends
        
        # Fix any obvious artifacts
        clean_text = clean_text.replace('&amp;', '&')
        clean_text = clean_text.replace('&quot;', '"')
        clean_text = clean_text.replace('&apos;', "'")
        clean_text = clean_text.replace('&lt;', '<')
        clean_text = clean_text.replace('&gt;', '>')

        return clean_text

    except Exception as e:
        raise Exception(f"Error processing transcript: {str(e)}")

# get_video_subtitles(sys.argv[1])


ydl_opts = {
    'skip_download': True,
    'writesubtitles': True,
    'writeautomaticsubs': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'referer': 'https://www.youtube.com/',
    'subtitleslangs': ['en', 'en-US'],
    # 'subtitlesformat': 'vtt',
    'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s')
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(video_url, download=False)
    
    # Check for and download subtitles
    if 'subtitles' in info and ('en' in info['subtitles'] or 'en-US' in info['subtitles']):
        logging.info("Manual English subtitles found. Downloading...")
        ydl.download([video_url])
    elif 'automatic_captions' in info and ('en' in info['automatic_captions'] or 'en-US' in info['automatic_captions']):
        logging.info("Automatic English captions found. Downloading...")
        
        for format in info["automatic_captions"]["en"]:
            if format["ext"] == "srv1":
                vtt_url = format["url"]
                break
        
        response = requests.get(vtt_url)
        if response.status_code == 200:
            content = response.text
            print(extract_transcript_text(content))
        
    else:
        logging.warning(f"No English subtitles or captions available for video: {video_id}")