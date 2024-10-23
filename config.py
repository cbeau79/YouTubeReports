import os

class Config:
    SECRET_KEY = str(os.environ.get('SECRET_KEY'))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max-limit
    IMAGES_FOLDER = 'i'
    
    # YouTube API configuration
    YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
    MAX_VIDEOS_TO_FETCH = 50
    MAX_VIDEOS_FOR_SUBTITLES = 3

    # OpenAI configuration
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = 'gpt-4o-mini'
    MAX_TOKENS = 8000

    # Mail settings
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('EMAIL_USER') or 'lumina.app.help@gmail.com'
    MAIL_PASSWORD = os.environ.get('EMAIL_PASS') or 'lhcjexczpxiqdvlt'
    MAIL_DEFAULT_SENDER = 'noreply@luminaapp.com'