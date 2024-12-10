from fpdf import FPDF
import json
import textwrap
import re

class ReportPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Add Unicode font support
        self.add_font('DejaVu', '', 'fonts/DejaVuSansCondensed.ttf', uni=True)
        self.add_font('DejaVu', 'B', 'fonts/DejaVuSansCondensed-Bold.ttf', uni=True)
        self.set_auto_page_break(auto=True, margin=5)
        self.add_page()
        self.set_font('DejaVu', size=10)
        self._current_y = 20  # Track vertical position

    def add_title(self, title):
        """Add a title to the PDF"""
        self.set_font('DejaVu', 'B', 18)
        self.cell(0, 10, title, ln=True, align='C')
        self._current_y += 15
        self.set_y(self._current_y)

    def add_section(self, title, content):
        """Add a section with title and content"""
        # Section Title
        self.set_font('DejaVu', 'B', 14)
        self.cell(0, 10, title, ln=True)
        self._current_y += 10
        
        # Content
        self.set_font('DejaVu', '', 10)
        
        # Check if we need a new page
        if self._current_y > 250:  # Near bottom of page
            self.add_page()
            self._current_y = 20
        
        # Clean and prepare content
        content = self.clean_text(content)
        
        # Handle content paragraphs
        paragraphs = content.split('\n')
        for paragraph in paragraphs:
            # Wrap text to fit page width (adjust width based on font)
            wrapped_text = textwrap.fill(paragraph, width=100)  # Reduced width for larger font
            
            for line in wrapped_text.split('\n'):
                if self._current_y > 270:  # Check for page break
                    self.add_page()
                    self._current_y = 20
                self.set_y(self._current_y)
                self.multi_cell(0, 10, line)
                self._current_y = self.get_y()
            
            self._current_y += 2  # Space between paragraphs

    def clean_text(self, text):
        """Clean text for PDF compatibility"""
        # Replace bullet points with dashes
        text = text.replace('•', '-')
        # Remove any other problematic characters
        text = re.sub(r'[^\x00-\x7F\u2022\u2013\u2014]', '', text)
        return text.strip()

def generate_channel_report_pdf(report_data, raw_channel_data):
    """Generate PDF for channel report"""
    try:
        pdf = ReportPDF()
        
        # Load JSON data
        if isinstance(report_data, str):
            report = json.loads(report_data)
        else:
            report = report_data

        if isinstance(raw_channel_data, str):
            channel_data = json.loads(raw_channel_data)
        else:
            channel_data = raw_channel_data

        # Add title
        pdf.add_title(f"Channel Analysis: {channel_data['title']}")

        # Channel Info
        stats_text = (
            f"Subscribers: {channel_data['subscriber_count']}\n"
            f"Total Views: {channel_data['total_view_count']}\n"
            f"Videos: {channel_data['total_video_count']}"
        )
        pdf.add_section("Channel Statistics", stats_text)

        # Process each section from the report
        for section in report['consultation_report']['sections']:
            if isinstance(section['content'], list) and section['content']:
                # Handle nested sections
                for subsection in section['content'][0]['sections']:
                    if subsection['content']:  # Only add if there's content
                        pdf.add_section(f"{subsection['subtitle']}", subsection['content'])
            elif section['content']:  # Direct content (like limitations)
                pdf.add_section(section['subtitle'], section['content'])

        return pdf

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise

def generate_video_summary_pdf(summary_data, raw_video_data):
    """Generate PDF for video summary"""
    try:
        pdf = ReportPDF()
        
        # Load JSON data
        if isinstance(summary_data, str):
            summary = json.loads(summary_data)
        else:
            summary = summary_data

        if isinstance(raw_video_data, str):
            video_data = json.loads(raw_video_data)
        else:
            video_data = raw_video_data

        # Add title
        pdf.add_title(f"Video Summary: {summary['title']}")

        # Video Info
        stats_text = (
            f"Views: {video_data['views']}\n"
            f"Likes: {video_data['like_count']}\n"
            f"Comments: {video_data['comment_count']}"
        )
        pdf.add_section("Video Statistics", stats_text)

        # Overview
        pdf.add_section("Overview", summary['overview'])

        # Key Points
        key_points_text = ""
        for point in summary['key_points']:
            key_points_text += f"- {point['point_title']}\n{point['point_description']}\n\n"
        pdf.add_section("Key Points", key_points_text)

        # Engagement Analysis
        pdf.add_section("Engagement Analysis", summary['engagement_analysis'])

        # Discourse Summary
        pdf.add_section("Discourse Summary", summary['discourse_summary'])

        # Target Audience
        pdf.add_section("Target Audience", summary['target_audience'])

        # Improvement Suggestions
        suggestions_text = ""
        for suggestion in summary['improvement_suggestions']:
            suggestions_text += f"- {suggestion['improvement_title']}\n{suggestion['improvement_description']}\n\n"
        pdf.add_section("Improvement Suggestions", suggestions_text)

        return pdf

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        raise

def generate_channel_report_markdown(report_data, raw_channel_data):
    """Generate Markdown for channel report"""
    # Load JSON data
    if isinstance(report_data, str):
        report = json.loads(report_data)
    else:
        report = report_data

    if isinstance(raw_channel_data, str):
        channel_data = json.loads(raw_channel_data)
    else:
        channel_data = raw_channel_data

    markdown = []
    
    # Title and Channel Info
    markdown.append(f"# Channel Analysis: {channel_data['title']}\n")
    markdown.append("## Channel Statistics\n")
    markdown.append(f"- Subscribers: {channel_data['subscriber_count']}")
    markdown.append(f"- Total Views: {channel_data['total_view_count']}")
    markdown.append(f"- Videos: {channel_data['total_video_count']}\n")

    # Process report sections
    for section in report['consultation_report']['sections']:
        if isinstance(section['content'], list) and section['content']:
            # Handle nested sections
            markdown.append(f"## {section['subtitle']}\n")
            for subsection in section['content'][0]['sections']:
                if subsection['content']:
                    markdown.append(f"### {subsection['subtitle']}\n")
                    # Handle content that might be a string or a list
                    if isinstance(subsection['content'], list):
                        markdown.append('\n'.join(subsection['content']) + '\n')
                    else:
                        markdown.append(f"{subsection['content']}\n")
        elif section['content']:  # Direct content (like limitations)
            markdown.append(f"## {section['subtitle']}\n")
            # Handle content that might be a string or a list
            if isinstance(section['content'], list):
                markdown.append('\n'.join(section['content']) + '\n')
            else:
                markdown.append(f"{section['content']}\n")

    # Add categorization if available
    if 'categorisation' in report['consultation_report']:
        markdown.append("## Content Categories\n")
        cats = report['consultation_report']['categorisation'][0]
        
        if cats.get('content_categories'):
            markdown.append("### Primary Categories\n")
            for cat in cats['content_categories']:
                markdown.append(f"- {cat}")
            markdown.append("")
        
        if cats.get('video_formats'):
            markdown.append("### Video Formats\n")
            for format in cats['video_formats']:
                markdown.append(f"- {format}")
            markdown.append("")
        
        if cats.get('content_category_justification'):
            markdown.append("### Justification\n")
            markdown.append(cats['content_category_justification'] + "\n")

    return "\n".join(markdown)

def generate_video_summary_markdown(summary_data, raw_video_data):
    """Generate Markdown for video summary"""
    # Load JSON data
    if isinstance(summary_data, str):
        summary = json.loads(summary_data)
    else:
        summary = summary_data

    if isinstance(raw_video_data, str):
        video_data = json.loads(raw_video_data)
    else:
        video_data = raw_video_data

    markdown = []
    
    # Title and Video Info
    markdown.append(f"# Video Summary: {summary['title']}\n")
    markdown.append("## Video Statistics\n")
    markdown.append(f"- Views: {video_data['views']}")
    markdown.append(f"- Likes: {video_data['like_count']}")
    markdown.append(f"- Comments: {video_data['comment_count']}")
    markdown.append(f"- Published: {video_data['date_published']}\n")

    # Overview
    markdown.append("## Overview\n")
    markdown.append(f"{summary['overview']}\n")

    # Key Points
    markdown.append("## Key Points\n")
    for point in summary['key_points']:
        markdown.append(f"### {point['point_title']}")
        markdown.append(f"{point['point_description']}\n")

    # Engagement Analysis
    markdown.append("## Engagement Analysis\n")
    markdown.append(f"{summary['engagement_analysis']}\n")

    # Discourse Summary
    markdown.append("## Discourse Summary\n")
    markdown.append(f"{summary['discourse_summary']}\n")

    # Discourse Themes
    markdown.append("## Discussion Themes\n")
    for theme in summary['discourse_themes']:
        markdown.append(f"### {theme['theme_title']}")
        markdown.append(f"{theme['theme_description']}\n")

    # Target Audience
    markdown.append("## Target Audience\n")
    markdown.append(f"{summary['target_audience']}\n")

    # Improvement Suggestions
    markdown.append("## Improvement Suggestions\n")
    for suggestion in summary['improvement_suggestions']:
        markdown.append(f"### {suggestion['improvement_title']}")
        markdown.append(f"{suggestion['improvement_description']}\n")

    return "\n".join(markdown)