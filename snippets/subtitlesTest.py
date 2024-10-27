import yt_dlp
import os

def get_yt_dlp_opts():
    # Add these options to help bypass anti-bot measures
    return {
        'nocheckcertificate': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'quiet': False,
        'no_color': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'cookiefile': 'youtube_cookies.txt',
        'no_cache_dir': True
    }

def list_available_subtitles(video_url):
    ydl_opts = get_yt_dlp_opts()
    ydl_opts.update({
        'listsubtitles': True,
        'skip_download': True,
    })
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
            if 'subtitles' in info:
                print("Available subtitles:")
                for lang, subtitles in info['subtitles'].items():
                    print(f"  {lang}: {[sub['ext'] for sub in subtitles]}")
            else:
                print("No subtitles available for this video.")
        except Exception as e:
            print(f"An error occurred: {str(e)}")

def download_subtitles(video_url, language='en'):
    ydl_opts = get_yt_dlp_opts()
    ydl_opts.update({
        'skip_download': True,
        'writesubtitles': True,
        'subtitleslangs': [language],
        'outtmpl': '%(title)s.%(ext)s'
    })
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=True)
            print(f"Subtitles downloaded for: {info['title']}")
        except Exception as e:
            print(f"An error occurred: {str(e)}")

# Replace 'VIDEO_URL' with the actual YouTube video URL
video_url = 'https://www.youtube.com/watch?v=ZT9NpPe0wRg'

# List available subtitles
list_available_subtitles(video_url)

# Uncomment the following line to download subtitles
download_subtitles(video_url, language='en-US')