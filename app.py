# Import necessary modules
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from youtube_utils import extract_channel_id, fetch_channel_data
from openai_utils import generate_channel_report
import json

# Initialize Flask app
app = Flask(__name__)

# Configure app settings
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Replace with a real secret key for production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'  # Use SQLite for simplicity in MVP
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Disable modification tracking for performance

# Initialize SQLAlchemy for database management
db = SQLAlchemy(app)

# Set up Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Specify the route for the login page

# Define User model for database
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Store hashed passwords

# Define Report model for database
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.String(100), nullable=False)
    channel_title = db.Column(db.String(200), nullable=False)
    report_data = db.Column(db.Text, nullable=False)

# User loader function for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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

# Route for user dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    reports = Report.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard.html', reports=reports)

# Route for analyzing YouTube channels
@app.route('/analyze', methods=['POST'])
@login_required
def analyze():
    try:
        data = request.get_json()
        if not data or 'channel_url' not in data:
            return jsonify({'error': 'Invalid request. Please provide a channel_url.'}), 400

        channel_url = data['channel_url']
        channel_id = extract_channel_id(channel_url)

        if not channel_id:
            return jsonify({'error': 'Invalid YouTube channel URL'}), 400

        channel_data = fetch_channel_data(channel_id)

        if not channel_data:
            return jsonify({'error': 'Unable to fetch channel data'}), 500

        channel_title = channel_data.get('title', 'Unknown Channel')

        report_json = generate_channel_report(channel_data)

        if not report_json:
            return jsonify({'error': 'Failed to generate channel report'}), 500

        # Save the report to the database with both channel_id and channel_title
        new_report = Report(
            user_id=current_user.id, 
            channel_id=channel_id,
            channel_title=channel_title,
            report_data=report_json
        )
        db.session.add(new_report)
        db.session.commit()

        return jsonify({'report': json.loads(report_json), 'report_id': new_report.id})

    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

# Run the app
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables before running the app
    app.run(host='0.0.0.0', port=5000, debug=True)  # Run in debug mode for development