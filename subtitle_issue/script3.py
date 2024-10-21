from youtube_transcript_api import YouTubeTranscriptApi
import json
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)

def get_video_subtitles(video_id):
    try:
        # Fetch the transcript
        transcript = YouTubeTranscriptApi.get_transcript(video_id)

        # Convert transcript to SRT format
        srt_content = ""
        for i, entry in enumerate(transcript, start=1):
            start = entry['start']
            duration = entry['duration']
            text = entry['text'].replace('\n', ' ')
            end = start + duration

            srt_content += f"{i}\n"
            srt_content += f"{format_time(start)} --> {format_time(end)}\n"
            srt_content += f"{text}\n\n"

        # Save the subtitles to a file
        with open(f"youtube_subtitles_{video_id}.srt", "w", encoding="utf-8") as f:
            f.write(srt_content)

        logging.info(f"Subtitles saved to youtube_subtitles_{video_id}.srt")

        # Also save the raw transcript data
        with open(f"youtube_transcript_{video_id}.json", "w", encoding="utf-8") as f:
            json.dump(transcript, f, ensure_ascii=False, indent=2)

        logging.info(f"Raw transcript saved to youtube_transcript_{video_id}.json")

        return srt_content

    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        return None

def format_time(seconds):
    """Convert seconds to SRT time format"""
    hours = int(seconds / 3600)
    minutes = int((seconds % 3600) / 60)
    seconds = seconds % 60
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{int(seconds):02d},{milliseconds:03d}"

def main():
    video_id = "dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    subtitles = get_video_subtitles(video_id)

    if subtitles:
        print("Subtitles fetched successfully. Check the SRT file for content.")
        print(subtitles[:500])  # Print the first 500 characters
    else:
        print("Failed to fetch subtitles.")

if __name__ == "__main__":
    main()
