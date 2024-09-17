# Import necessary modules
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response, stream_with_context
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from youtube_utils import extract_channel_id, fetch_channel_data
from openai_utils import generate_channel_report
import json
import os
import time
from datetime import datetime
from pytz import timezone
from config import Config

app = Flask(__name__)

app.config.from_object(Config)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Define your models here (User, Report, etc.)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_title = db.Column(db.String(200), nullable=False)
    report_data = db.Column(db.Text, nullable=False)
    raw_channel_data = db.Column(db.Text, nullable=True)
    date_created = db.Column(db.DateTime, nullable=False)

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Helper function to get current time in local timezone
def get_local_time():
    local_tz = timezone('US/Pacific')  # Replace with your local timezone
    return datetime.now(local_tz)

# Route for the home page
@app.route('/')
def index():
    return render_template('index.html')

# Route for user registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user:
            flash('Username already exists')
            return redirect(url_for('register'))
        
        # Use 'pbkdf2:sha256' method for password hashing
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful. Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

# Route for user logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# Analyze Route
@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    def generate():
        try:
            data = request.get_json()
            if not data or 'channel_url' not in data:
                yield json.dumps({'error': 'Invalid request. Please provide a channel_url.'}) + '\n'
                return

            channel_url = data['channel_url']
            yield json.dumps({'progress': 'Extracting channel ID...'}) + '\n'
            channel_id = extract_channel_id(channel_url)

            if not channel_id:
                yield json.dumps({'error': 'Invalid YouTube channel URL'}) + '\n'
                return
            
            yield json.dumps({'progress': f'Channel ID: {channel_id}'}) + '\n'
            yield json.dumps({'progress': 'Fetching channel data...'}) + '\n'
            channel_data = fetch_channel_data(channel_id)

            if not channel_data:
                yield json.dumps({'error': 'Unable to fetch channel data'}) + '\n'
                return

            channel_title = channel_data.get('title', 'Unknown Channel')
            yield json.dumps({'progress': f'Analyzing channel: {channel_title}'}) + '\n'

            yield json.dumps({'progress': 'Generating report...'}) + '\n'
            report_json = generate_channel_report(channel_data)

            if not report_json:
                yield json.dumps({'error': 'Failed to generate channel report'}) + '\n'
                return

            new_report = Report(
                user_id=current_user.id, 
                channel_id=channel_id,
                channel_title=channel_title,
                report_data=report_json,
                raw_channel_data=json.dumps(channel_data),
                date_created=get_local_time()
            )
            db.session.add(new_report)
            db.session.commit()

            yield json.dumps({'progress': 'Report generated and saved.'}) + '\n'
            yield json.dumps({
                'report': json.loads(report_json),
                'report_id': new_report.id,
                'channel_title': channel_title,
                'avatar_url': channel_data['avatar_url']
            }) + '\n'

        except Exception as e:
            yield json.dumps({'error': f'An unexpected error occurred: {str(e)}'}) + '\n'

    return Response(stream_with_context(generate()), content_type='application/json')


# Dashboard route
@app.route('/dashboard')
@login_required
def dashboard():
    reports = Report.query.filter_by(user_id=current_user.id).order_by(Report.date_created.desc()).all()
    return render_template('dashboard.html', reports=reports)

# Get Report route
@app.route('/report/<int:report_id>')
@login_required
def get_report(report_id):
    report = Report.query.get(report_id)
    if report and report.user_id == current_user.id:
        return jsonify({
            'report': json.loads(report.report_data),
            'date_created': report.date_created.isoformat()
        })
    else:
        return jsonify({'error': 'Report not found'}), 404

# Run the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables before running the app
    app.run(host='0.0.0.0', port=5000, debug=True)  # Run in debug mode for development