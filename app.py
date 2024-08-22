# app.py
from flask import Flask, render_template, request, jsonify
from youtube_utils import extract_channel_id, fetch_channel_data, generate_channel_report
import traceback
import logging
import os
from datetime import datetime
import json

app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def index():
    return render_template('index.html')

def save_report_to_file(channel_id, report):
    # Create a 'reports' directory if it doesn't exist
    if not os.path.exists('reports'):
        os.makedirs('reports')
    
    # Generate a filename with timestamp and channel ID
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reports/report_{timestamp}_{channel_id}.json"
    
    # Save the report as a JSON file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    app.logger.info(f"Report saved to {filename}")
    return filename

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()
        
        if not data or 'channel_url' not in data:
            return jsonify({'error': 'Invalid request. Please provide a channel_url.'}), 400
        
        channel_url = data['channel_url']
        app.logger.info(f"Received request to analyze channel: {channel_url}")
        
        channel_id = extract_channel_id(channel_url)
        
        if not channel_id:
            app.logger.warning(f"Invalid YouTube channel URL: {channel_url}")
            return jsonify({'error': 'Invalid YouTube channel URL'}), 400
        
        app.logger.info(f"Extracted channel ID: {channel_id}")
        
        channel_data = fetch_channel_data(channel_id)
        
        if not channel_data:
            app.logger.error(f"Unable to fetch channel data for channel ID: {channel_id}")
            return jsonify({'error': 'Unable to fetch channel data'}), 500
        
        app.logger.info(f"Successfully fetched channel data for channel ID: {channel_id}")
        
        report_json = generate_channel_report(channel_data)
        
        if not report_json:
            app.logger.error("Failed to generate channel report")
            return jsonify({'error': 'Failed to generate channel report'}), 500
        
        app.logger.info("Successfully generated channel report")
        
        # Parse the JSON string into a Python dictionary
        try:
            report_dict = json.loads(report_json)
        except json.JSONDecodeError as e:
            app.logger.error(f"Failed to parse JSON report: {e}")
            return jsonify({'error': 'Failed to parse JSON report', 'details': str(e)}), 500
        
        # Save the report to a file
        saved_filename = save_report_to_file(channel_id, report_dict)
        app.logger.info(f"Report saved to file: {saved_filename}")
        
        return jsonify({'report': report_dict, 'saved_file': saved_filename})
    
    except Exception as e:
        app.logger.error(f"An unexpected error occurred: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)