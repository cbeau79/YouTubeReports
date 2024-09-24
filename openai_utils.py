from openai import OpenAI
import json
from config import Config
import os

# Load app parameters
def load_config():
    try:
        with open('config.json', 'r') as config_file:
            return json.load(config_file)
    except FileNotFoundError:
        print("Configuration file 'config.json' not found. Please create it and add your settings.")
        exit(1)
    except json.JSONDecodeError:
        print("Error parsing 'config.json'. Please make sure it's valid JSON.")
        exit(1)

# Load configuration
app_config = load_config()

# Use configuration values
API_KEY = os.environ.get('YOUTUBE_API_KEY')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
MAX_VIDEOS = app_config['max_videos_to_fetch']
MAX_VIDEOS_FOR_SUBTITLES = app_config['max_videos_for_subtitles']
OPENAI_MODEL = app_config['openai_model']
MAX_TOKENS = app_config['max_tokens']

client = OpenAI(api_key=OPENAI_API_KEY)

# report_data is a JSON formatted file containing channel data
def generate_channel_report(channel_data):
    # Load JSON report template
    with open('json_template_report.json') as f:
        json_template_report = json.load(f)
    
    # Craft the prompt
    prompt = f"""
    You are a YouTube content consultant. Analyze the following complete YouTube channel data and provide a comprehensive report. The data is provided in JSON format:

    {channel_data}

    Analyze this data and present the key findings in the following format: 

    1. Executive Summary
        1. Content summary (1 paragraph)
        2. Channel hosts and personalities (1 paragraph - if you don't know anything about the hosts and personalities, it's ok to say so)
        3. Channel prominence and competitive landscape (1 paragraph)
    2. Key Metrics: 
        1. Average views per video (1 paragraph of context - how does this compare in the channel's competitive space?)
        2. Top-performing video category 
        3. Average number of videos published per week (1 paragraph of context - how does this compare in the channel's competitive space?)
    3. Trends: 
        1. List 3 notable trends, each with a paragraph of explanation.
    4. Oratry style:
        1. Using the subtitle data only, do an analysis of the oratry style of the videos. It should be three paragraphs long. For each point, use an example quote from the subtitle text for illustration. Use sub-headings for each paragraph.
    5. Recommendations: 
        1. Provide 3 data-driven recommendations, each with a paragraph of rationale.
    6. Limitations:
        1. If you identify any limitations in the data provided, please mention them here.

    Provide your analysis in a clear, structured format.
    Use specific data points to support your insights and recommendations. 
    If you identify any limitations in the data provided, please mention them.
    Do not rush to come up with an answer, take your time.

    Return in JSON. 

    Use this JSON template to format the results:

    {json_template_report}
    """

    # Interface with OpenAI
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a helpful YouTube content consultant who responds in JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000
        )

        returned_string = response.choices[0].message.content 
        # json_data = json.loads(returned_string)
        # formated_string = returned_string.encode().decode('unicode_escape')
        # print(formated_string)

        return returned_string
    except Exception as e:
        print(f"An error occurred while generating the report: {e}")
        return ""

# report_data is a JSON formatted file containing channel data
def generate_video_summary(video_data):
    
    # Load JSON summary template
    with open('json_template_summary.json') as f:
        json_template_summary = json.load(f)

    # Craft the prompt
    my_prompt = f"""
    You are a YouTube content consultant. Analyze the following data about a YouTube video. The data is provided in JSON format:

    {video_data}

    Write a summary of this video. 
    Provide at least 5 bullet points, but use as many as you need to, each with a detailed explanation and citing examples used in the original text.

    Provide your analysis in a clear, structured format.
    
    Do not rush to come up with an answer, take your time. Return your answer in JSON.
    """

    #Claude prompt
    prompt = f"""
    You are a YouTube content analyst. Analyze the following data about a YouTube video and provide a comprehensive summary. The data is provided in JSON format:

    {json.dumps(video_data, indent=2)}

    Please provide a summary of this video that includes the following:
    1. A brief overview of the video's content (2-3 sentences)
    2. Key points or main topics discussed in the video (bullet points - but go into as much detail as necessary to fully articulate the point. avoid simply summarising the point. instead, summarise and explain it. Use as many bullet points as you need to.)
    3. Your analysis of the video's engagement (views, likes, comments) in the context of the channel's typical performance
    4. Potential audience or target demographic for this content
    5. Suggestions for improvement or expansion of the topic (2-3 ideas)

    Provide your analysis in a clear, structured format. Take your time to answer, don't rush.

    Return in JSON. 

    Use this JSON template to format the results:
    {json_template_summary}
    """

    # Interface with OpenAI
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a helpful YouTube content analyst who provides video summaries in JSON format."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000
        )

        summary = response.choices[0].message.content
        # Ensure the summary is valid JSON
        # json.loads(summary)  # This will raise an exception if the summary is not valid JSON
        json_data = json.loads(summary)
        # formated_string = summary.encode().decode('unicode_escape')
        
        print(json_data)
        
        return summary

    except Exception as e:
        print(f"An error occurred while generating the video summary: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {str(e)}"})
