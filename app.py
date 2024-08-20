# app.py
from flask import Flask, render_template, request, jsonify
from youtube_utils import extract_channel_id, fetch_channel_data, generate_channel_report

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
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
    
    report = generate_channel_report(channel_data)
    
    return jsonify({'report': report})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
