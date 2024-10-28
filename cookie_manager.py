import logging
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path
import yt_dlp

class CookieValidator:
    def __init__(self, cookie_path: str):
        self.cookie_path = Path(cookie_path)
        self.logger = logging.getLogger(__name__)

    def check_status(self):
        """Check if cookies exist and are valid."""
        try:
            if not self.cookie_path.exists():
                return False, "Cookie file not found"

            # Test the cookies with a simple request
            test_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiefile': str(self.cookie_path),
                'extract_flat': True,
                'skip_download': True,
                'no_write_download_archive': True,
                'no_cache_dir': True,
                'no_config': True,
                'cookiesfrombrowser': None,
            }
            
            # Ensure we can read the cookie file
            self.cookie_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            
            with yt_dlp.YoutubeDL(test_opts) as ydl:
                self.logger.debug("Testing cookie validity with YouTube request...")
                try:
                    result = ydl.extract_info(
                        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        download=False,
                        process=False
                    )
                    if result and 'title' in result:
                        self.logger.debug(f"Successfully validated cookies with video: {result.get('title')}")
                        return True, "Cookies are valid"
                    else:
                        self.logger.debug("Failed to extract video info")
                        return False, "Failed to validate cookies with YouTube request"
                except Exception as e:
                    error_msg = str(e).lower()
                    self.logger.error(f"Error during validation request: {error_msg}")
                    if any(term in error_msg for term in ['cookie', 'sign in', 'login', 'authorization']):
                        return False, "Cookies are expired or invalid"
                    return False, f"Error validating cookies: {str(e)}"

        except Exception as e:
            self.logger.error(f"Unexpected error in cookie validation: {str(e)}")
            return False, f"Unexpected error in cookie validation: {str(e)}"