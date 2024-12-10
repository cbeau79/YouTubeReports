from openai import OpenAI
import json
from config import Config
import os

# Use configuration values
API_KEY = Config.YOUTUBE_API_KEY # os.environ.get('YOUTUBE_API_KEY')
OPENAI_API_KEY = Config.OPENAI_API_KEY # os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = Config.OPENAI_MODEL # app_config['openai_model']
MAX_TOKENS = Config.MAX_TOKENS # app_config['max_tokens']

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_watch_history(history_data):
    """Analyze watch history data using OpenAI."""
    prompt = f"""You are a skilled psychologist analyzing a person's YouTube watch history. 
    The data shows the last 200 videos they've watched. Based on this data, provide deep psychological insights about their personality, interests, and behaviors.
    
    Watch History Data:
    {json.dumps(history_data, indent=2)}
    
    Analyze this watch history and provide insights in the following areas:
    1. Key personality traits evident from their viewing choices
    2. Primary interests and what they reveal about the person
    3. Emotional patterns in their content consumption
    4. Learning style and intellectual preferences
    5. Cultural preferences and social values
    6. Behavioral patterns and potential motivations
    7. Personalized recommendations for personal growth
    
    Ensure your analysis is:
    - Professional but accessible
    - Based on clear patterns in the data
    - Focused on constructive insights
    - Respectful of privacy and avoiding overly personal assumptions
    
    Return your analysis in this exact JSON structure:
    {{
        "personality_traits": ["trait1", "trait2", "trait3", ...],
        "primary_interests": ["interest1", "interest2", "interest3", ...],
        "emotional_patterns": "Detailed analysis of emotional patterns",
        "learning_style": "Analysis of learning preferences and patterns",
        "cultural_preferences": "Analysis of cultural and social preferences",
        "behavioral_insights": "Key behavioral patterns and motivations",
        "recommendations": ["recommendation1", "recommendation2", "recommendation3", ...]
    }}
    """

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are an insightful psychologist who analyzes YouTube viewing patterns."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logging.error(f"Error in analyze_watch_history: {str(e)}")
        return json.dumps({"error": str(e)})

# report_data is a JSON formatted file containing channel data
def generate_channel_report(channel_data):
    # Load JSON report template
    try:
        with open('json_template_report_v2.json', 'r') as f:
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
    <instructions>
        Role: You are a YouTube content consultant.
        Objective:
            - Analyse the YouTube channel data in <channel_data> and generate a concise report that prioritises actionable insight.
            - Provide findings in bullet points rather than sentences, such as:
                Point 1
                Point 2
                Point 3
            - Classify the content using the lists in <content_categories> and <video_formats>:
                1. content_categories: Select up to three categories from <Content Categories> that best describe the channel, ordered by relevance.
                2. video_formats: Identify the primary video format(s) from <Video Formats>. List up to three formats, in order of prevalence, if multiple are used frequently.
                3. content_category_justification: Explain in 2–3 sentences why you chose these categories and formats, specifying which content elements informed your selection. 
                Include this classification in the categorisation section of <return_json_template>.
        Tone: Write in a clear, structured, and concise style that appeals to YouTube content creators. Avoid passive phrasing. Be constructive yet direct, especially when identifying areas for improvement.
        Other Instructions:
            - Highlight specific strengths, weaknesses, and areas of improvement.
            - Support insights and recommendations with concrete data.
            - Provide thoughtful, concise answers, and avoid rushing to conclusions.
            - Provide your answers in bullet points for each section of the report.
        Report Structure: 
            1. Executive Summary (At least 3 bullet points for each section)
                1. Content summary: 3 bullet points that answer the following questions:
                    - What subject matter does this channel use in its content?
                    - What video formats does this channel use to deliver its content?
                    - What is the most noteable thing about this channel? If there is nothing noteable, point that out as a failing.
                2. Channel hosts and personalities: Describe the hosts if they are mentioned in the data. If not, indicate this. Incorporate any relevant external knowledge.
                3. Channel prominence and competitive landscape: Analyse the channel’s success or limitations in its niche.
            2. Key Metrics (At least 3 bullet points for each section)
                1. Viewership: List average and median views. Review view counts, likes, and comments for different video types, identifying successful formats or inconsistencies.
                2. Top-performing content category and video format: Based on <Content Categories> and <Video Formats>, identify the best-performing category and format, using series or franchise names where applicable.
                3. Publishing frequency: Note the channel’s average weekly uploads and compare with similar channels, listing the primary competitors.
            3. Trends (At least 3 bullet points for each section):
                1. Recent trends: List 3 notable content trends evident in the <channel_data>, each with a short sentence of explanation.
                2. Successful video formats: Explain what the channel's most successful video format is and why it's working for them.
                3. Trajectory: Analyze whether the channel is growing or shrinking and give some reasoning as to why.
            4. Stylistic Choices (At least 3 bullet points for each section):
                1. Oratory style: Using subtitle data, provide 3 bullet points of analysis of the channel’s oratory style. Include relevant quotes from subtitles (2–3 sentences each) to illustrate your points.
                2. Titles: Using video title data, provide 3 bullet points of analysis of the channels approach to titling its videos.
                3. Descriptions: Using description data, provide 3 bullet points of analysis of the channels approach to writing descriptions.
            5. Recommendations (At least 3 bullet points for each section):
                - Offer three growth recommendations, with data-backed reasoning for each. Focus on strategies for rapid growth, either by refining the current approach or pivoting as needed. Reference strategies used by competitors where applicable.
            6. Limitations:
                - Highlight any data limitations you identify in <channel_data>.
    </instructions>
    
    <content_categories>
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
    </content_categories>

    <video_formats>
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
    </video_formats>

    Use this JSON template to format your results:

    <return_json_template>
        {json_template_report}
    </return_json_template>

    <channel_data>
        {channel_data_str}
    </channel_data>
    """

    with open('prompt.txt', 'w') as file:
        file.write(prompt)

    prompt_chars = len(prompt)
    est_tokens = prompt_chars/4

    print(f"Length of prompt: {prompt_chars} - Estimated token length: {est_tokens}")

    # Interface with OpenAI - o1-mini
    '''try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )'''
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a helpful YouTube content consultant who responds in JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10000
        )

        returned_string = response.choices[0].message.content 
        with open('output.txt', 'w') as file:
            file.write(returned_string)
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
    <role>
        - You are an expert at taking notes.
    </role>
    <instructions>
        - **Generate a set of concise, structured notes** from the content in <video_data> below 
        - **Focus directly on the core insights** from the video. 
        - Use **active voice** to state these insights clearly. Avoid passive constructions (e.g., "it explores," "the video discusses") and unnecessary detachment. 
        - Eliminate any extraneous or filler language. Only include the **most critical points** that help to explain the core ideas. 
        - **Write notes as if you're a student** summarizing the main ideas of the video, capturing the most important insights and explanations. 
        - The notes should allow the reader to **understand the content and ideas clearly**.
        - Structure your notes as follows:
            1. **Overview**: Provide a 2-3 sentence summary of the video's content, stating the key theme or message. 
            2. **Key Points and Insights**: Provide **at least 10 bullet points** with detailed insights directly from the video. Use the **active voice** and present insights directly. If relevant, include **direct quotes** from the video, but only if the quotes help explain the idea and are **at least 2-3 sentences long**. 
            3. **Engagement Analysis**: Analyze the video's **engagement** (views, likes, comments) in the context of the channel’s typical performance. 
            4. **Discourse Summary**: Summarize the **top 100 comments** in **one sentence**. Capture the general tone and main themes in the conversation. 
            5. **Discourse Themes**: List 3-4 **detailed bullet points** summarizing the main discussion topics in the comments. 
            6. **Target Audience**: Identify the potential **audience or target demographic** for this content. Who is this video likely aimed at? 
            7. **Improvement Suggestions**: Provide 2-3 **actionable suggestions** for improving the video, but **focus on content-related suggestions** rather than visual or technical elements.
        - Return in JSON. 
        - Use this JSON template to format the results:
        <results_format>
            {json_template_summary}
        </results_format>
    </instructions>
    <video_data>
    {json.dumps(video_data, indent=2)}
    </video_data>
    """

    # Interface with OpenAI
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are an expert at taking notes."},
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


### OLD IDEAS

'''
    prompt = f"""
    <instructions>
    Role: You are a YouTube content consultant. 
    Function: 
        1. Analyze the YouTube channel data provided in <channel_data> and create a comprehensive report that focuses on insight and understanding.
        2. Using the lists in <content_categories> and <video_formats>, provide the following information:
            - content_categories: Select up to three categories from the <Content Categories> list that best describe the channel. List them in order of relevance.
            - video_formats: Identify the primary video format(s) used by the channel from the <Video Formats> list. If multiple formats are used frequently, list up to three in order of prevalence.
            - content_category_justification: Provide a brief explanation (2-3 sentences) for your categorization choices. What specific elements of the content led you to select these categories and formats?
            Include this categorization information using the section of the <return_json_template> labelled 'categorisation'.
    
    Writing style: Provide your analysis in a clear, structured format. You are a consultant, but use an approachable, friendly writing style that is recongisable to a YouTube audience.
    
    Other instructions:
    - Don't shy away from criticism: if a channel is making mistakes then point them out.
    - Use specific data points to support your insights and recommendations. 
    - Do not rush to come up with an answer, take your time.
    </instructions>

    <channel_data>
    {channel_data_str}
    </channel_data>

    <report_format>
    1. Executive Summary
        1. Content summary (1 or 2 paragraphs - summarise the content strategy being used and why this channel is being successful or failing.)
        2. Channel hosts and personalities (1 or 2 paragraphs - if you don't know anything about the hosts and personalities, it's ok to say so. If you have knowledge about the hosts and personalities outside of the provided data, please feel free to use that information.)
        3. Channel prominence and competitive landscape (1 or 2 paragraphs - detail what makes this channel a success or failure in its niche.)
    2. Key Metrics: 
        1. Viwership (List average views and median views. Carefully examine the view counts, likes, and comments on different types of video and assess whether the channel has a consistent format that is successful. For example, if most of their videos receive a low amount of views but some of their videos get lots of views, use this in your analysis. 1 or 2 paragraphs.)
        2. Top-performing content category and video format (1 or 2 paragraphs. Using the lists of <Content Categories> and <Video Formats> detailed below, specify which content category and which video formats are most successful on this channel. In particular, determine which video formats the channel is seeing success with and list them out, using the channels franchise names or series titles if they have them.) 
        3. Average number of videos published per week (1 or 2 paragraphs of context - how does this compare in the channel's competitive space? List the channels primary competitors.)
    3. Trends: 
        1. Recent trends: List 3 notable content trends evident in the <channel_data>, each with a short sentence of explanation.
        2. Successful video formats: Explain what the channel's most successful video format is and why it's working for them.
        3. Trajectory: Analyze whether the channel is growing or shrinking and give some reasoning as to why.
    4. Oratry style:
        1. Using the subtitle data only, carry out an analysis of the oratry style of the videos. It should be three paragraphs long. Use sub-headings for each paragraph. Use quotes from the subtitles to support your analysis but ensure they are at least 2 to 3 sentences in length.
    5. Recommendations: 
        1. Provide 3 data-driven recommendations for growth of the channel, each with a paragraph of rationale. Focus your answers on how this channel in particular can grow quickly, either by relying on their current strategy, or by pivoting to another strategy. If there are other channels in their niche that are being more successful, explain how this channel could emulate their success.
    6. Limitations:
        1. If you identify any limitations in the data provided, please mention them here.
    </report_format>

    <content_categories>
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
    </content_categories>

    <video_formats>
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
    </video_formats>

    Use this JSON template to format your results:

    <return_json_template>
    {json_template_report}
    </return_json_template>
    """'''

'''    # Interface with OpenAI
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={ "type": "json_object" },
            messages=[
                {"role": "user", "content": prompt}
            ],
        ){"role": "system", "content": "You are a helpful YouTube content consultant who responds in JSON."},'''
