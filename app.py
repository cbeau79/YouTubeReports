# Import necessary modules
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response, stream_with_context, send_from_directory, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from flask_mail import Mail, Message
from sqlalchemy.exc import SQLAlchemyError
import os
import json
from datetime import datetime, timedelta
from pytz import timezone
from config import Config
from youtube_utils import extract_channel_id, fetch_channel_data, extract_video_id, get_video_data
from openai_utils import generate_channel_report, generate_video_summary
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.config.from_object(Config)

# Configure logging
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/lumina.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info('Lumina startup')

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
mail = Mail(app)

# Helper function to get current time in local timezone
def get_local_time():
    return datetime.now(timezone('US/Pacific'))

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    report_accesses = db.relationship('UserReportAccess', back_populates='user')
    video_accesses = db.relationship('UserVideoAccess', back_populates='user')

    def __init__(self, email, password):
        self.email = email
        self.set_password(password)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def get_reset_token(self, expires_sec=1800):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='password-reset-salt')

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, salt='password-reset-salt', max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def delete_account(self):
        UserReportAccess.query.filter_by(user_id=self.id).delete()
        UserVideoAccess.query.filter_by(user_id=self.id).delete()
        db.session.delete(self)
        db.session.commit()

    @property
    def username(self):
        return self.email

    @property
    def video_summaries(self):
        return VideoSummary.query.join(UserVideoAccess).filter(UserVideoAccess.user_id == self.id)

class ChannelReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(100), unique=True, nullable=False)
    channel_title = db.Column(db.String(200), nullable=False)
    report_data = db.Column(db.Text, nullable=False)
    raw_channel_data = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime(timezone=True), nullable=False, default=get_local_time)
    user_accesses = db.relationship('UserReportAccess', back_populates='report')
    content_categories = db.Column(db.JSON, nullable=True)
    video_formats = db.Column(db.JSON, nullable=True)
    content_category_justification = db.Column(db.Text, nullable=True)

    def set_categorization(self, categorization):
        self.content_categories = categorization['content_categories']
        self.video_formats = categorization['video_formats']
        self.content_category_justification = categorization['content_category_justification']

    def get_categorization(self):
        return {
            'content_categories': self.content_categories,
            'video_formats': self.video_formats,
            'content_category_justification': self.content_category_justification,
        }

class UserReportAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    report_id = db.Column(db.Integer, db.ForeignKey('channel_report.id'), nullable=False)
    date_accessed = db.Column(db.DateTime(timezone=True), nullable=False, default=get_local_time)
    user = db.relationship('User', back_populates='report_accesses')
    report = db.relationship('ChannelReport', back_populates='user_accesses')
    __table_args__ = (db.UniqueConstraint('user_id', 'report_id', name='uq_user_report'),)

class VideoSummary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_id = db.Column(db.String(100), unique=True, nullable=False)
    video_title = db.Column(db.String(200), nullable=False)
    summary_data = db.Column(db.Text, nullable=False)
    raw_video_data = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime(timezone=True), nullable=False, default=get_local_time)
    user_accesses = db.relationship('UserVideoAccess', back_populates='summary')

class UserVideoAccess(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    summary_id = db.Column(db.Integer, db.ForeignKey('video_summary.id'), nullable=False)
    date_accessed = db.Column(db.DateTime(timezone=True), nullable=False, default=get_local_time)
    user = db.relationship('User', back_populates='video_accesses')
    summary = db.relationship('VideoSummary', back_populates='user_accesses')
    __table_args__ = (db.UniqueConstraint('user_id', 'summary_id', name='uq_user_video'),)

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Jinja2 filters
@app.template_filter('from_json')
def from_json(value):
    return json.loads(value)

@app.template_filter('days_ago')
def days_ago(date):
    if date.tzinfo is None:
        date = timezone('US/Pacific').localize(date)
    now = get_local_time()
    return (now - date).days

# Helper function to save JSON data to file
def save_json_to_file(data, channel_id):
    if not os.path.exists('channel_data'):
        os.makedirs('channel_data')
    
    timestamp = get_local_time().strftime("%Y%m%d_%H%M%S")
    filename = f"channel_data/channel_data_{timestamp}_{channel_id}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"Channel data saved to {filename}")
    return filename

def seed_user_account(user_id):
    # List of pre-selected channel IDs and video IDs for seeding
    sample_channel_ids = ['', '', '']
    sample_video_ids = ['', '', '']

    try:
        user = User.query.get(user_id)
        if not user:
            current_app.logger.error(f"User with ID {user_id} not found")
            return False

        # Seed channel reports
        for channel_id in sample_channel_ids:
            report = ChannelReport.query.filter_by(channel_id=channel_id).first()
            if report:
                access = UserReportAccess(user_id=user.id, report_id=report.id)
                db.session.add(access)

        # Seed video summaries
        for video_id in sample_video_ids:
            summary = VideoSummary.query.filter_by(video_id=video_id).first()
            if summary:
                access = UserVideoAccess(user_id=user.id, summary_id=summary.id)
                db.session.add(access)

        db.session.commit()
        current_app.logger.info(f"Successfully seeded account for user {user_id}")
        return True
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Database error seeding account for user {user_id}: {str(e)}")
        return False
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Unexpected error seeding account for user {user_id}: {str(e)}")
        return False

# Routes
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['IMAGES_FOLDER'], filename)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze')
@login_required
def analyze():
    return render_template('analyze.html')

@app.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update':
            current_user.first_name = request.form.get('first_name')
            current_user.last_name = request.form.get('last_name')
            
            new_password = request.form.get('new_password')
            if new_password:
                current_user.set_password(new_password)
            
            db.session.commit()
            flash('Your account has been updated.', 'success')
        
        elif action == 'delete':
            current_user.delete_account()
            logout_user()
            flash('Your account has been deleted.', 'info')
            return redirect(url_for('index'))
    
    return render_template('account.html', user=current_user)

@app.route('/reports')
@login_required
def reports():
    # Fetch user's channel report accesses
    user_report_accesses = UserReportAccess.query.filter_by(user_id=current_user.id).order_by(UserReportAccess.date_accessed.desc()).all()
    
    # Fetch video summaries for the current user
    user_video_accesses = UserVideoAccess.query.filter_by(user_id=current_user.id).order_by(UserVideoAccess.date_accessed.desc()).all()
    
    combined_data = []
    
    # Process channel reports
    for access in user_report_accesses:
        combined_data.append({
            'type': 'channel_report',
            'item': access.report,
            'date_accessed': access.date_accessed,
            'date_created': access.report.date_created
        })
    
    # Process video summaries
    for access in user_video_accesses:
        combined_data.append({
            'type': 'video_summary',
            'item': access.summary,
            'date_accessed': access.date_accessed,
            'date_created': access.summary.date_created
        })
    
    # Sort combined data by date accessed, most recent first
    combined_data.sort(key=lambda x: x['date_created'], reverse=True)
    
    # Check for new report or summary
    new_report_id = request.args.get('new_report')
    new_summary_id = request.args.get('new_summary')
    
    # If there's a new report or summary, get its data
    new_item = None
    if new_report_id:
        new_item = next((item for item in combined_data if item['type'] == 'channel_report' and str(item['item'].id) == new_report_id), None)
    elif new_summary_id:
        new_item = next((item for item in combined_data if item['type'] == 'video_summary' and str(item['item'].id) == new_summary_id), None)
    
    return render_template('reports.html', 
                           combined_data=combined_data, 
                           new_item=new_item, 
                           new_report_id=new_report_id, 
                           new_summary_id=new_summary_id)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('register'))
        
        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists')
            return redirect(url_for('register'))
        
        new_user = User(email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

def send_reset_email(user):
    token = user.get_reset_token()
    msg = Message('Password Reset Request',
                  sender=app.config['MAIL_DEFAULT_SENDER'],
                  recipients=[user.email])
    msg.body = f'''To reset your password, visit the following link:
{url_for('reset_token', token=token, _external=True)}

If you did not make this request then simply ignore this email and no changes will be made.
'''
    try:
        print(f"Attempting to send email to {user.email}")
        print(f"MAIL_SERVER: {app.config['MAIL_SERVER']}")
        print(f"MAIL_PORT: {app.config['MAIL_PORT']}")
        print(f"MAIL_USE_TLS: {app.config['MAIL_USE_TLS']}")
        print(f"MAIL_USERNAME: {app.config['MAIL_USERNAME']}")
        print(f"MAIL_DEFAULT_SENDER: {app.config['MAIL_DEFAULT_SENDER']}")
        # Don't print the actual password, just check if it's set
        print(f"MAIL_PASSWORD is set: {'Yes' if app.config['MAIL_PASSWORD'] else 'No'}")
        
        mail.send(msg)
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        # You might want to log this error or handle it appropriately
        raise  # Re-raise the exception to see the full traceback

@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('reports'))
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
        flash('An email has been sent with instructions to reset your password.', 'info')
        return redirect(url_for('login'))
    return render_template('reset_request.html')

@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('reports'))
    user = User.verify_reset_token(token)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if password != confirm_password:
            flash('Passwords do not match.')
            return redirect(url_for('reset_token', token=token))
        user.set_password(password)
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template('reset_token.html', token=token)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        app.logger.debug(f"Form data: {request.form}")
        email = request.form.get('email')  # Changed from 'username' to 'email'
        password = request.form.get('password')
        
        app.logger.debug(f"Extracted email: {email}")
        app.logger.debug(f"Extracted password: {'*' * len(password) if password else None}")
        
        user = User.query.filter_by(email=email).first()
        app.logger.debug(f"Login attempt for email: {email}")
        app.logger.debug(f"User found: {user is not None}")
        
        if user and user.check_password(password):
            login_user(user)
            app.logger.debug("Login successful")
            return redirect(url_for('reports'))
        else:
            app.logger.debug("Invalid email or password")
            flash('Invalid email or password')
        
    return render_template('login.html')

@app.route('/debug_user/<email>')
def debug_user(email):
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({
            'email': user.email,
            'password_hash': user.password,
            'id': user.id
        })
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/analyze_channel', methods=['POST'])
@login_required
def analyze_channel():
    def generate():
        try:
            data = request.get_json()
            if not data or 'channel_url' not in data:
                yield json.dumps({'error': 'Invalid request. Please provide a channel_url.'}) + '\n'
                return

            channel_url = data['channel_url']
            yield json.dumps({'progress': 'Extracting channel ID ...'}) + '\n'
            channel_id = extract_channel_id(channel_url)

            if not channel_id:
                yield json.dumps({'error': 'Invalid YouTube channel URL'}) + '\n'
                return
            
            yield json.dumps({'progress': f'Channel ID: {channel_id}'}) + '\n'

            # Check if a fresh report exists
            existing_report = ChannelReport.query.filter_by(channel_id=channel_id).first()
            
            if existing_report:
                yield json.dumps({'progress': 'Existing report found. Retrieving data...'}) + '\n'
                report_data = json.loads(existing_report.report_data)
                channel_data = json.loads(existing_report.raw_channel_data)
                channel_title = channel_data.get('title', 'Unknown Channel')
            else:
                yield json.dumps({'progress': 'Fetching channel data ...'}) + '\n'
                channel_data = fetch_channel_data(channel_id)

                if not channel_data:
                    yield json.dumps({'error': 'Unable to fetch channel data'}) + '\n'
                    return

                channel_title = channel_data.get('title', 'Unknown Channel')
                yield json.dumps({'progress': f'Analyzing channel: {channel_title}'}) + '\n'

                yield json.dumps({'progress': 'Generating report (can take a minute) ...'}) + '\n'
                report_json = generate_channel_report(channel_data)

                if not report_json:
                    yield json.dumps({'error': 'Failed to generate channel report'}) + '\n'
                    return

                report_data = json.loads(report_json)
                
                # Extract categorization data
                categorization = report_data['consultation_report']['categorisation'][0]

                # Create new report
                existing_report = ChannelReport(
                    channel_id=channel_id,
                    channel_title=channel_title,
                    report_data=report_json,
                    raw_channel_data=json.dumps(channel_data)
                )
                existing_report.set_categorization(categorization)
                db.session.add(existing_report)
                db.session.commit()

            # Create or update UserReportAccess
            user_access = UserReportAccess.query.filter_by(user_id=current_user.id, report_id=existing_report.id).first()
            if not user_access:
                user_access = UserReportAccess(user_id=current_user.id, report_id=existing_report.id)
                db.session.add(user_access)
            else:
                user_access.date_accessed = get_local_time()
            db.session.commit()

            yield json.dumps({'progress': 'Report retrieved and added to your reports.'}) + '\n'
            yield json.dumps({
                'report': report_data,
                'report_id': existing_report.id,
                'channel_title': channel_title,
                'avatar_url': channel_data['avatar_url'],
                'redirect_url': url_for('reports', new_report=existing_report.id)
            }) + '\n'

        except Exception as e:
            app.logger.error(f"An error occurred: {str(e)}")
            yield json.dumps({'error': f'An unexpected error occurred: {str(e)}'}) + '\n'

    return Response(stream_with_context(generate()), content_type='application/json')

@app.route('/report/<int:report_id>')
@login_required
def get_report(report_id):
    try:
        report = ChannelReport.query.get(report_id)
        user_access = UserReportAccess.query.filter_by(user_id=current_user.id, report_id=report_id).first()
        
        if report and user_access:
            # Update last access time
            user_access.date_accessed = get_local_time()
            db.session.commit()
            
            return jsonify({
                'report': json.loads(report.report_data),
                'raw_channel_data': json.loads(report.raw_channel_data) if report.raw_channel_data else None,
                'date_created': report.date_created.isoformat(),
                'categorization': report.get_categorization()
            })
        else:
            app.logger.warning(f"Report {report_id} not found or access denied for user {current_user.id}")
            return jsonify({'error': 'Report not found or access denied'}), 404
    except Exception as e:
        app.logger.error(f"Error in get_report: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@app.route('/summary/<int:summary_id>')
@login_required
def get_summary(summary_id):
    try:
        summary = VideoSummary.query.get(summary_id)
        if summary:
            # Check if the current user has access to this summary
            user_access = UserVideoAccess.query.filter_by(user_id=current_user.id, summary_id=summary_id).first()
            if user_access:
                return jsonify({
                    'summary': json.loads(summary.summary_data),
                    'video_id': summary.video_id,
                    'video_title': summary.video_title,
                    'date_created': summary.date_created.isoformat(),
                    'raw_data': json.loads(summary.raw_video_data)
                })
            else:
                app.logger.warning(f"User {current_user.id} attempted to access summary {summary_id} without permission")
                return jsonify({'error': 'Access denied'}), 403
        else:
            app.logger.warning(f"Summary {summary_id} not found")
            return jsonify({'error': 'Summary not found'}), 404
    except Exception as e:
        app.logger.error(f"Error in get_summary: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500
    
@app.route('/summarize')
@login_required
def summarize():
    return render_template('summarize.html')

@app.route('/summarize_video', methods=['POST'])
@login_required
def summarize_video():
    def generate():
        try:
            data = request.get_json()
            if not data or 'video_url' not in data:
                yield json.dumps({'type': 'error', 'message': 'Invalid request. Please provide a video_url.'}) + '\n'
                return

            video_url = data['video_url']
            yield json.dumps({'type': 'progress', 'message': 'Extracting video ID ...'}) + '\n'
            video_id = extract_video_id(video_url)

            if not video_id:
                yield json.dumps({'type': 'error', 'message': 'Invalid YouTube video URL'}) + '\n'
                return
            
            yield json.dumps({'type': 'progress', 'message': f'Video ID: {video_id}'}) + '\n'

            # Check if a summary already exists for this video
            existing_summary = VideoSummary.query.filter_by(video_id=video_id).first()
            
            if existing_summary:
                yield json.dumps({'type': 'progress', 'message': 'Existing summary found. Retrieving data...'}) + '\n'
                
                # Check if the current user already has access to this summary
                user_access = UserVideoAccess.query.filter_by(user_id=current_user.id, summary_id=existing_summary.id).first()
                
                if not user_access:
                    # If not, create a new access entry
                    new_user_access = UserVideoAccess(user_id=current_user.id, summary_id=existing_summary.id)
                    db.session.add(new_user_access)
                    db.session.commit()
                    yield json.dumps({'type': 'progress', 'message': 'Summary associated with your account.'}) + '\n'
                else:
                    yield json.dumps({'type': 'progress', 'message': 'Summary already in your account.'}) + '\n'

                summary_data = json.loads(existing_summary.summary_data)
                raw_data = json.loads(existing_summary.raw_video_data)

                yield json.dumps({'type': 'summary', 'data': {
                    'summary': summary_data,
                    'video_id': existing_summary.video_id,
                    'video_title': existing_summary.video_title,
                    'raw_data': raw_data,
                    'redirect_url': url_for('reports', new_summary=existing_summary.id)
                }}) + '\n'
                return

            yield json.dumps({'type': 'progress', 'message': 'Fetching video data ...'}) + '\n'
            video_data = get_video_data(video_id)

            if not video_data:
                yield json.dumps({'type': 'error', 'message': 'Unable to fetch video data'}) + '\n'
                return

            video_title = video_data[0].get('title', 'Unknown Video')
            yield json.dumps({'type': 'progress', 'message': f'Summarizing video: {video_title}'}) + '\n'

            yield json.dumps({'type': 'progress', 'message': 'Generating summary (can take a minute) ...'}) + '\n'
            summary_json = generate_video_summary(video_data[0])
            
            try:
                summary = json.loads(summary_json)
            except json.JSONDecodeError as e:
                app.logger.error(f"Failed to parse summary JSON: {str(e)}")
                yield json.dumps({'type': 'error', 'message': 'Failed to generate a valid summary'}) + '\n'
                return

            if 'error' in summary:
                yield json.dumps({'type': 'error', 'message': summary['error']}) + '\n'
                return

            app.logger.info(f"Summary generated for video {video_id}")

            # Create new summary
            new_summary = VideoSummary(
                video_id=video_id,
                video_title=video_title,
                summary_data=summary_json,
                raw_video_data=json.dumps(video_data[0])
            )
            db.session.add(new_summary)
            db.session.flush()  # This will assign an ID to new_summary

            # Create access for the current user
            new_user_access = UserVideoAccess(user_id=current_user.id, summary_id=new_summary.id)
            db.session.add(new_user_access)
            db.session.commit()

            yield json.dumps({'type': 'progress', 'message': 'Summary generated and saved.'}) + '\n'
            yield json.dumps({'type': 'summary', 'data': {
                'summary': summary,
                'video_id': video_id,
                'video_title': video_title,
                'raw_data': video_data[0],
                'redirect_url': url_for('reports', new_summary=new_summary.id)
            }}) + '\n'

        except Exception as e:
            app.logger.error(f"An error occurred in summarize_video: {str(e)}")
            yield json.dumps({'type': 'error', 'message': f'An unexpected error occurred: {str(e)}'}) + '\n'

    return Response(stream_with_context(generate()), content_type='application/json')

# Run the app (dev mode only)
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables before running the app
    app.run(host='0.0.0.0', port=5000, debug=True)  # Run in debug mode for development