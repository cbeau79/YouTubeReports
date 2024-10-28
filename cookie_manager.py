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

    def verify_cookie_content(self):
        """Verify cookie file contents with improved parsing."""
        try:
            with open(self.cookie_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = [line.strip() for line in content.split('\n') if line.strip() and not line.startswith('#')]
                self.logger.info(f"Cookie file has {len(lines)} valid cookie entries")
                
                # Track both direct cookies and secure variants
                key_cookies = {
                    'LOGIN_INFO': False,
                    'VISITOR_INFO1_LIVE': False,
                    'YSC': False,
                    'CONSENT': False,
                    '__Secure-3PSID': False,
                    '__Secure-3PAPISID': False,
                    'PREF': False
                }
                
                for line in lines:
                    try:
                        # Split the line into its components
                        parts = line.split('\t')
                        if len(parts) >= 7:  # Valid cookie lines should have at least 7 parts
                            domain, subdomain, path, secure, expiry, name, value = parts[:7]
                            
                            # Check for both direct and secure cookie variants
                            if name in key_cookies:
                                key_cookies[name] = True
                                self.logger.info(f"Found cookie: {name}")
                            # Also check if we have secure variants as alternatives
                            elif name.startswith('__Secure-') and name[9:] in key_cookies:
                                base_name = name[9:]
                                key_cookies[base_name] = True
                                self.logger.info(f"Found secure variant for: {base_name}")
                    except Exception as e:
                        self.logger.warning(f"Skipping malformed cookie line: {line[:30]}... Error: {str(e)}")
                        continue
                
                # Check what's missing
                missing_cookies = [name for name, found in key_cookies.items() if not found]
                
                # Special handling for alternative authentication cookies
                if 'LOGIN_INFO' in missing_cookies and any(x in str(content) for x in ['SAPISID', '__Secure-3PAPISID']):
                    missing_cookies.remove('LOGIN_INFO')
                    self.logger.info("Found alternative authentication cookie (SAPISID)")
                
                if missing_cookies:
                    self.logger.warning(f"Missing important cookies: {', '.join(missing_cookies)}")
                else:
                    self.logger.info("All essential cookies present")
                
                # Return True if we have enough critical cookies
                required_cookies = {'VISITOR_INFO1_LIVE', 'PREF', '__Secure-3PSID'}
                has_required = all(any(cookie in str(content) for cookie in [name, f'__Secure-{name}']) 
                                 for name in required_cookies)
                
                return has_required
                
        except Exception as e:
            self.logger.error(f"Error reading cookie file: {str(e)}")
            return False

    def check_status(self):
        """Check if cookies exist and are valid with improved error handling."""
        try:
            if not self.cookie_path.exists():
                return False, "Cookie file not found"

            # Verify cookie contents first
            if not self.verify_cookie_content():
                return False, "Missing essential cookies"

            # Test the cookies with a simple request
            test_opts = {
                'quiet': True,
                'no_warnings': True,
                'cookiefile': str(self.cookie_path),
                'extract_flat': True,
                'skip_download': True,
                'no_write_download_archive': True,
                'no_cache_dir': True,
                'cookiesfrombrowser': None,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                },
                'socket_timeout': 30,
                'retries': 3
            }
            
            with yt_dlp.YoutubeDL(test_opts) as ydl:
                self.logger.debug("Testing cookie validity with YouTube request...")
                try:
                    info = ydl.extract_info(
                        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        download=False,
                        process=False
                    )
                    
                    if info and ('title' in info or 'entries' in info):
                        self.logger.info("Cookie validation successful")
                        return True, "Cookies are valid"
                    else:
                        self.logger.warning("Failed to extract video info")
                        return False, "Failed to validate cookies with YouTube request"
                        
                except Exception as e:
                    error_msg = str(e).lower()
                    self.logger.error(f"Error during validation request: {error_msg}")
                    if any(term in error_msg for term in ['cookie', 'sign in', 'login', 'authorization', 'bot']):
                        return False, "Cookies are expired or invalid"
                    return False, f"Error validating cookies: {str(e)}"

        except Exception as e:
            self.logger.error(f"Unexpected error in cookie validation: {str(e)}")
            return False, f"Unexpected error in cookie validation: {str(e)}"