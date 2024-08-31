from openai import OpenAI
import json

# Load report JSON template
with open('json_template.json') as f:
    json_template = json.load(f)

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
config = load_config()

# Use configuration values
API_KEY = config['youtube_api_key']
OPENAI_API_KEY = config['openai_api_key']
MAX_VIDEOS = config['max_videos_to_fetch']
MAX_VIDEOS_FOR_SUBTITLES = config['max_videos_for_subtitles']
OPENAI_MODEL = config['openai_model']
MAX_TOKENS = config['max_tokens']

client = OpenAI(api_key=OPENAI_API_KEY)

# report_data is a JSON formatted file containing channel data
def generate_channel_report(channel_data):
    
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

    {json_template}
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
        formated_string = returned_string.encode().decode('unicode_escape')
        print(formated_string)

        return returned_string
    except Exception as e:
        print(f"An error occurred while generating the report: {e}")
        return ""

# report_data is a JSON formatted file containing channel data
def generate_video_summary(video_data):
    
    # Craft the prompt
    prompt = f"""
    You are a YouTube content consultant. Analyze the following data about a YouTube video. The data is provided in JSON format:

    {video_data}

    Write a summary of this video. 
    Provide at least 5 bullet points, but use as many as you need to, each with a detailed explanation and citing examples used in the original text.

    Provide your analysis in a clear, structured format.
    
    Do not rush to come up with an answer, take your time.
    """

    # Interface with OpenAI
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            # response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a helpful YouTube researcher who is summarising videos for note taking"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000
        )

        returned_string = response.choices[0].message.content 
        # json_data = json.loads(returned_string)
        # formated_string = returned_string.encode().decode('unicode_escape')
        # print(formated_string)

        print("NO")

        return returned_string
    except Exception as e:
        print(f"An error occurred while generating the report: {e}")
        return ""
