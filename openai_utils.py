from openai import OpenAI
import json
from config import Config
import os

# Load app parameters
'''
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
'''

# Use configuration values
API_KEY = Config.YOUTUBE_API_KEY # os.environ.get('YOUTUBE_API_KEY')
OPENAI_API_KEY = Config.OPENAI_API_KEY # os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = Config.OPENAI_MODEL # app_config['openai_model']
MAX_TOKENS = Config.MAX_TOKENS # app_config['max_tokens']

client = OpenAI(api_key=OPENAI_API_KEY)

# report_data is a JSON formatted file containing channel data
def generate_channel_report(channel_data):
    # Load JSON report template
    try:
        with open('json_template_report.json', 'r') as f:
            json_template_report = json.load(f)
    except Exception as e:
        print(f"Error loading template: {e}")
        return None

    # Convert channel_data to JSON string if it's not already
    if isinstance(channel_data, dict):
        channel_data_str = json.dumps(channel_data, indent=2)
    else:
        channel_data_str = channel_data

    ## To debug the channel data, un-comment this
    # with open('channel_data_dump.json', 'w', encoding='utf-8') as f:
    #     print(channel_data_str)
    
    # Craft the prompt
    prompt = f"""
    You are a YouTube content consultant. Analyze the following YouTube channel data and provide a comprehensive report that focuses on insight and understanding. The data is provided in JSON format:

    <channel_data>
    {channel_data_str}
    </channel_data>
    
    Analyze the above data and present the key insights in the following format: 

    1. Executive Summary
        1. Content summary (1 or 2 paragraphs - summarise the content strategy being used and why this channel is being successful or failing.)
        2. Channel hosts and personalities (1 or 2 paragraphs - if you don't know anything about the hosts and personalities, it's ok to say so. If you have knowledge about the hosts and personalities outside of the provided data, please feel free to use that information.)
        3. Channel prominence and competitive landscape (1 or 2 paragraphs - detail what makes this channel a success or failure in its niche.)
    2. Key Metrics: 
        1. Viwership (List average views and median views. Carefully examine the view counts, likes, and comments on different types of video and assess whether the channel has a consistent format that is successful. For example, if most of their videos receive a low amount of views but some of their videos get lots of views, use this in your analysis. 1 or 2 paragraphs.)
        2. Top-performing content category and video format (1 or 2 paragraphs. Using the lists of <Content Categories> and <Video Formats> detailed below, specify which content category and which video formats are most successful on this channel. In particular, determine which video formats the channel is seeing success with and list them out, using the channels franchise names or series titles if they have them.) 
        3. Average number of videos published per week (1 or 2 paragraphs of context - how does this compare in the channel's competitive space? List the channels primary competitors.)
    3. Trends: 
        1. List 3 notable content trends evident in the <channel_data>, each with a paragraph of explanation.
    4. Oratry style:
        1. Using the subtitle data only, carry out an analysis of the oratry style of the videos. It should be three paragraphs long. Use sub-headings for each paragraph. Use quotes from the subtitles to support your analysis but ensure they are at least 2 to 3 sentences in length.
    5. Recommendations: 
        1. Provide 3 data-driven recommendations for growth of the channel, each with a paragraph of rationale. Focus your answers on how this channel in particular can grow quickly, either by relying on their current strategy, or by pivoting to another strategy. If there are other channels in their niche that are being more successful, explain how this channel could emulate their success.
    6. Limitations:
        1. If you identify any limitations in the data provided, please mention them here.

    Provide your analysis in a clear, structured format.
    Use specific data points to support your insights and recommendations. 
    Do not rush to come up with an answer, take your time.

    When analyzing the YouTube channel please categorize it according to the following lists:

    <Content Categories>
    Entertainment
    Education
    Gaming
    Music
    News & Politics
    Science & Technology
    Lifestyle & How-To
    Sports
    Travel & Events
    Comedy
    Film & Animation
    Automotive
    Pets & Animals
    Food & Cooking
    Beauty & Fashion
    Fitness & Health
    Business & Finance
    Arts & Crafts
    Vlogs & Personal
    Family & Parenting
    </Content Categories>

    <Video Formats>
    Tutorial/How-To
    Review
    Vlog
    Let's Play (Gaming)
    Unboxing
    Reaction
    Interview
    Podcast
    Storytelling/Narrative
    Music Video
    Comedy Sketch
    News Report
    Documentary
    Live Stream
    Q&A
    Challenge
    Compilation
    Explainer
    Product Demonstration
    Debate/Discussion
    </Video Formats>

    Please provide the following information:

    content_categories: Select up to three categories from the <Content Categories> list that best describe the channel. List them in order of relevance.
    video_formats: Identify the primary video format(s) used by the channel from the <Video Formats> list. If multiple formats are used frequently, list up to three in order of prevalence.
    content_category_justification: Provide a brief explanation (2-3 sentences) for your categorization choices. What specific elements of the content led you to select these categories and formats?

    Please include this categorization information in your analysis of the YouTube channel, using the section of the JSON template labelled 'categorisation'.

    Use this JSON template to format your results:

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
            max_tokens=8000
        )

        returned_string = response.choices[0].message.content 
        return returned_string
    except Exception as e:
        print(f"An error occurred while generating the report: {e}")
        return ""

# report_data is a JSON formatted file containing channel data
def generate_video_summary(video_data):
    
    # Load JSON summary template
    with open('json_template_summary.json') as f:
        json_template_summary = json.load(f)

    # Prompt
    prompt = f"""
    You are an expert at taking notes and copy editing. Analyze the following JSON formatted data about a YouTube video:

    <video_data>
    {json.dumps(video_data, indent=2)}
    </video_data>

    Please generate a set of structured notes about this video. Use the active voice. These notes should enable the reader to understand the content and ideas in the video. 
    
    Structure your notes in the following way:

    1. Overview: A brief overview of the video's content (2-3 sentences).
    2. Key points and insights from the video (Provide at least 10 bullet points, but use as many as you need to. Write at least one paragraph of explanation for each point. Use the active voice. Be detailed and help the reader to understand the insight clearly. If quotes from the text support or help to explain the insight then include the quote, but ensure that the quote is relevant and at least 2 or 3 sentences long.).
    3. Engagement analysis: Your analysis of the video's engagement (views, likes, comments) in the context of the channel's typical performance.
    4. Discourse summary: Using the top 100 comments as your source, provide 1 sentence that summarises the discussion in the comments - what's the nature of the conversation?
    5. Discourse themes: 3 or 4 detailed bullet points on the conversation in the comments - what themes have developed in the discussion?
    6. Target audience: Potential audience or target demographic for this content. Who is the video aimed at?
    7. Improvement suggestions: 2 or 3 bullet points that detail suggestions for improvements to the video. Avoid suggestions about visual elements such as graphs and graphics.

    Take your time to answer, don't rush.

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


