from youtube_utils import get_video_data
from urllib.parse import urlparse, parse_qs
from openai_utils import generate_video_summary
import json

print("""
----------------------------
- YOUTUBE VIDEO SUMMARIZER -
----------------------------
v0.1 by Chris Beaumont
""")

def extract_video_id(url):
    query = urlparse(url).query
    params = parse_qs(query)
    return params.get('v', [None])[0]

while True:
    video_url = input("\n\nENTER YOUTUBE VIDEO URL: ")
   
    video_id = extract_video_id(video_url)
   
    print("Contacting YouTube API for data about video_id: " + video_id)
    video_data = get_video_data(video_id)
   
    print("Generating report with openai ...")
    summary_report = generate_video_summary(video_data)
    formatted_report = summary_report.encode().decode('unicode_escape')

    print("\nVIDEO SUMMARY REPORT\n-------------------- \n")
    print(formatted_report)