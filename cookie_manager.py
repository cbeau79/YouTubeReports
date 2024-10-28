import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
import yt_dlp

class CookieValidator:
    def __init__(self, cookie_path: str):
        self.cookie_path = Path(cookie_path)
        self.logger = logging.getLogger(__name__)

    def check_status(self):
        """
        Check if cookies exist and are fresh.
        Returns (is_valid, message)
        """
        try:
            if not self.cookie_path.exists():
                return False, "Cookie file not found"

            # Check file age
            # cookie_age = datetime.now() - datetime.fromtimestamp(self.cookie_path.stat().st_mtime)
            # if cookie_age > timedelta(hours=24):
            #     return False, f"Cookies are {cookie_age.total_seconds() // 3600:.1f} hours old"

            # Try a test request
            try:
                with yt_dlp.YoutubeDL({'quiet': True, 'cookiefile': str(self.cookie_path)}) as ydl:
                    # Try to fetch metadata for a known public video
                    ydl.extract_info("dQw4w9WgXcQ", download=False)
                    return True, "Cookies are valid"
            except Exception as e:
                error_msg = str(e).lower()
                if any(term in error_msg for term in ['cookie', 'sign in', 'login']):
                    return False, "Cookies are expired or invalid"
                return False, f"Cookie validation error: {str(e)}"

        except Exception as e:
            self.logger.error(f"Error checking cookies: {str(e)}")
            return False, f"Error checking cookies: {str(e)}"