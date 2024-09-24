# Import necessary modules
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response, stream_with_context, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from youtube_utils import extract_channel_id, fetch_channel_data, extract_video_id, get_video_data
from openai_utils import generate_channel_report, generate_video_summary
import json
import os
from datetime import datetime, timedelta
from pytz import timezone
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.config['IMAGES_FOLDER'] = 'i'
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Helper function to get current time in local timezone
def get_local_time():
    return datetime.now(timezone('US/Pacific'))

# Define models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    report_accesses = db.relationship('UserReportAccess', back_populates='user')

class ChannelReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(100), unique=True, nullable=False)
    channel_title = db.Column(db.String(200), nullable=False)
    report_data = db.Column(db.Text, nullable=False)
    raw_channel_data = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime(timezone=True), nullable=False, default=get_local_time)
    user_accesses = db.relationship('UserReportAccess', back_populates='report')

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

# Routes
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(app.config['IMAGES_FOLDER'], filename)

@app.route('/')
def index():
    return redirect(url_for('analyze'))

@app.route('/analyze')
@login_required
def analyze():
    return render_template('analyze.html')

@app.route('/reports')
@login_required
def reports():
    # Fetch user's channel report accesses
    user_report_accesses = UserReportAccess.query.filter_by(user_id=current_user.id).order_by(UserReportAccess.date_accessed.desc()).all()
    
    # Fetch all video summaries (assuming all users can access all summaries)
    video_summaries = VideoSummary.query.order_by(VideoSummary.date_created.desc()).all()
    
    unique_report_ids = set()
    combined_data = []
    
    # Process channel reports
    for access in user_report_accesses:
        if access.report_id not in unique_report_ids:
            combined_data.append({
                'type': 'channel_report',
                'item': access.report,
                'date_accessed': access.date_accessed,
                'date_created': access.report.date_created
            })
            unique_report_ids.add(access.report_id)
    
    # Process video summaries
    for summary in video_summaries:
        combined_data.append({
            'type': 'video_summary',
            'item': summary,
            'date_accessed': None,  # We don't track access for summaries
            'date_created': summary.date_created
        })
    
    # Sort combined data by date created, most recent first
    combined_data.sort(key=lambda x: x['date_created'], reverse=True)
    
    return render_template('reports.html', combined_data=combined_data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('analyze'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

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
                # Check if the user already has access to this report
                user_access = UserReportAccess.query.filter_by(user_id=current_user.id, report_id=existing_report.id).first()
                if not user_access:
                    # If the user doesn't have access, create a new UserReportAccess entry
                    user_access = UserReportAccess(user_id=current_user.id, report_id=existing_report.id)
                    db.session.add(user_access)
                else:
                    # If the user already has access, update the access time
                    user_access.date_accessed = get_local_time()
                db.session.commit()

                yield json.dumps({
                    'progress': 'Report retrieved.',
                    'report': json.loads(existing_report.report_data),
                    'report_id': existing_report.id,
                    'channel_title': existing_report.channel_title,
                    'avatar_url': json.loads(existing_report.raw_channel_data)['avatar_url']
                }) + '\n'
                return

            yield json.dumps({'progress': 'Fetching channel data ...'}) + '\n'
            channel_data = fetch_channel_data(channel_id)

            if not channel_data:
                yield json.dumps({'error': 'Unable to fetch channel data'}) + '\n'
                return

            channel_title = channel_data.get('title', 'Unknown Channel')
            save_json_to_file(channel_data, channel_title)
            yield json.dumps({'progress': f'Analyzing channel: {channel_title}'}) + '\n'

            yield json.dumps({'progress': 'Generating report (takes a minute) ...'}) + '\n'
            report_json = generate_channel_report(channel_data)

            if not report_json:
                yield json.dumps({'error': 'Failed to generate channel report'}) + '\n'
                return

            # Save or update the report
            if existing_report:
                existing_report.report_data = report_json
                existing_report.raw_channel_data = json.dumps(channel_data)
                existing_report.date_created = get_local_time()
                report = existing_report
            else:
                report = ChannelReport(
                    channel_id=channel_id,
                    channel_title=channel_title,
                    report_data=report_json,
                    raw_channel_data=json.dumps(channel_data)
                )
                db.session.add(report)
            
            db.session.commit()

            # Check if the user already has access to this report
            user_access = UserReportAccess.query.filter_by(user_id=current_user.id, report_id=report.id).first()
            if not user_access:
                # If the user doesn't have access, create a new UserReportAccess entry
                user_access = UserReportAccess(user_id=current_user.id, report_id=report.id)
                db.session.add(user_access)
            else:
                # If the user already has access, update the access time
                user_access.date_accessed = get_local_time()
            db.session.commit()

            yield json.dumps({'progress': 'Report generated and added to your reports.'}) + '\n'
            yield json.dumps({
                'report': json.loads(report_json),
                'report_id': report.id,
                'channel_title': channel_title,
                'avatar_url': channel_data['avatar_url']
            }) + '\n'

        except Exception as e:
            yield json.dumps({'error': f'An unexpected error occurred: {str(e)}'}) + '\n'

    return Response(stream_with_context(generate()), content_type='application/json')

@app.route('/report/<int:report_id>')
@login_required
def get_report(report_id):
    report = ChannelReport.query.get(report_id)
    user_access = UserReportAccess.query.filter_by(user_id=current_user.id, report_id=report_id).first()
    
    if report and user_access:
        # Update last access time
        user_access.date_accessed = get_local_time()
        db.session.commit()
        
        return jsonify({
            'report': json.loads(report.report_data),
            'date_created': report.date_created.isoformat()
        })
    else:
        return jsonify({'error': 'Report not found or access denied'}), 404

@app.route('/summary/<int:summary_id>')
@login_required
def get_summary(summary_id):
    summary = VideoSummary.query.get(summary_id)
    if summary:
        return jsonify({
            'summary': json.loads(summary.summary_data),
            'video_id': summary.video_id,
            'video_title': summary.video_title,
            'date_created': summary.date_created.isoformat(),
            'raw_data': json.loads(summary.raw_video_data)
        })
    else:
        return jsonify({'error': 'Summary not found'}), 404
    
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

            # Check if a summary already exists
            existing_summary = VideoSummary.query.filter_by(video_id=video_id).first()
            if existing_summary:
                app.logger.info(f"Existing summary found for video {video_id}")
                try:
                    summary_data = json.loads(existing_summary.summary_data)
                    raw_data = json.loads(existing_summary.raw_video_data)
                    yield json.dumps({'type': 'progress', 'message': 'Summary retrieved.'}) + '\n'
                    yield json.dumps({'type': 'summary', 'data': {
                        'summary': summary_data,
                        'video_id': existing_summary.video_id,
                        'video_title': existing_summary.video_title,
                        'raw_data': raw_data
                    }}) + '\n'
                except json.JSONDecodeError as e:
                    app.logger.error(f"Error decoding existing summary: {str(e)}")
                    yield json.dumps({'type': 'error', 'message': 'Error retrieving existing summary.'}) + '\n'
                return

            yield json.dumps({'type': 'progress', 'message': 'Fetching video data ...'}) + '\n'
            video_data = get_video_data(video_id)

            if not video_data:
                yield json.dumps({'type': 'error', 'message': 'Unable to fetch video data'}) + '\n'
                return

            video_title = video_data[0].get('title', 'Unknown Video')
            yield json.dumps({'type': 'progress', 'message': f'Summarizing video: {video_title}'}) + '\n'

            yield json.dumps({'type': 'progress', 'message': 'Generating summary ...'}) + '\n'
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

            # Save the summary
            new_summary = VideoSummary(
                video_id=video_id,
                video_title=video_title,
                summary_data=summary_json,
                raw_video_data=json.dumps(video_data[0])
            )
            db.session.add(new_summary)
            db.session.commit()

            yield json.dumps({'type': 'progress', 'message': 'Summary generated and saved.'}) + '\n'
            yield json.dumps({'type': 'summary', 'data': {
                'summary': summary,
                'video_id': video_id,
                'video_title': video_title,
                'raw_data': video_data[0]
            }}) + '\n'

        except Exception as e:
            app.logger.error(f"An error occurred: {str(e)}")
            yield json.dumps({'type': 'error', 'message': f'An unexpected error occurred: {str(e)}'}) + '\n'

    return Response(stream_with_context(generate()), content_type='application/json')

# Run the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables before running the app
    app.run(host='0.0.0.0', port=5000, debug=True)  # Run in debug mode for development