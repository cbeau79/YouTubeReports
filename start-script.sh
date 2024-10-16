#!/bin/bash

# Activate virtual environment (adjust path as necessary)
source /path/to/your/venv/bin/activate

# Set environment variables (or use a .env file)
export FLASK_APP=app.py
export FLASK_ENV=production

# Start Gunicorn
exec gunicorn -c gunicorn.conf.py app:app
