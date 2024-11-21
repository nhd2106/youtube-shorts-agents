from typing import TypedDict
import os
from openai import AsyncOpenAI
from typing import Optional

class VideoFormat(TypedDict):
    type: str  # 'shorts' or 'normal'
    duration: str  # '60s' for shorts, 'flexible' for normal

class Content(TypedDict):
    script: str
    title: str
    hashtags: list[str]
    format: VideoFormat

class ContentGenerator:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def generate_content(self, idea: str, video_format: str = "shorts") -> Content:
        try:
            # Define format specifications
            format_specs = {
                "shorts": {
                    "type": "shorts",
                    "duration": "60s",
                    "script_length": "60 - 75 seconds",
                    "style": "energetic and engaging"
                },
                "normal": {
                    "type": "normal",
                    "duration": "flexible",
                    "script_length": "2-10 minutes",
                    "style": "detailed and comprehensive"
                }
            }

            if video_format not in format_specs:
                raise ValueError(f"Invalid video format. Choose from: {list(format_specs.keys())}")

            format_spec = format_specs[video_format]

            # Update system prompt based on video format
            system_prompt = f"""You are a Vietnamese content creator specialized in creating {video_format} videos.
You must always respond in the exact format:
TITLE: [catchy Vietnamese title]
SCRIPT: [Vietnamese script]
HASHTAGS: [relevant hashtags]

Follow these guidelines:
1. Title:
    - Must be catchy, intriguing, and in Vietnamese
    - Should reflect the video's content and hook the audience

2. Script:
    - Start with an irresistible hook in the first 3 seconds using ONE of these:
      * A mind-blowing statistic that challenges common beliefs
      * A controversial "hot take" that makes viewers stop scrolling
      * A personal story that hits emotional pain points
      * An insightful tip that makes viewers think
      * A mind-blowing fact that surprises viewers
    - Use one of these storytelling techniques:
      * The Hero's Journey
      * The 7-Second Rule (7 seconds to make your point)
      * The 3-Step Framework 
      * The 5 Whys
      * The 2-Sentence Story
      * The 10-Second Rule
      * Rhyming sentences to make the script more engaging, like a song
    - Address specific user requests:
      * For history, include time and place details
      * For stories, provide meaningful narratives without abrupt endings
      * For facts, list 7-10 relevant facts about the topic
    - Ensure the script is:
      * In Vietnamese
      * {format_spec['script_length']} when read
      * {format_spec['style']}
      * Structured as: Attention-grabbing hook → Problem → Solution → Call to action
      * Concluding with "Nếu thấy video này hữu ích, đừng ngại bấm like và đăng ký để ủng hộ kênh!"
      * Ending with a question or prompt for the next video topic
    - do not include any icons 
3. Hashtags:
    - Mix relevant Vietnamese and English hashtags
    - Ensure they are trending and related to the video's content

4. General:
    - Be concise, engaging, and informative
    - Use current and accurate information
    - Aim to educate, entertain, or inspire the audience
"""

            # Make the API call
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # or "gpt-3.5-turbo" for lower cost
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create a {video_format} video script about: {idea}"}
                ],
                temperature=0.7,
                
            )
            
            # Get the content
            content = response.choices[0].message.content
            print("\nDebug - Raw API Response:")
            print(content)
            
            # Parse and return the content
            return self._parse_content(content, format_spec)
            
        except Exception as e:
            print(f"\nDebug - Error details: {str(e)}")
            raise

    def _parse_content(self, content: str, format_spec: dict) -> Content:
        """Helper method to parse the assistant's response"""
        title = ""
        script = ""
        hashtags = []
        current_section = None
        
        # Parse response line by line
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('TITLE:'):
                current_section = 'title'
                title = line.replace('TITLE:', '').strip()
            elif line.startswith('SCRIPT:'):
                current_section = 'script'
                script = line.replace('SCRIPT:', '').strip()
            elif line.startswith('HASHTAGS:'):
                current_section = 'hashtags'
                hashtags_str = line.replace('HASHTAGS:', '').strip()
                hashtags = [tag.strip() for tag in hashtags_str.split(',')]
            elif current_section == 'script':
                # Append to script if we're in script section
                script += '\n' + line
        
        # Validate content
        if not title or not script or not hashtags:
            print("\nDebug - Parsed Content:")
            print(f"Title: {title}")
            print(f"Script: {script}")
            print(f"Hashtags: {hashtags}")
            raise ValueError("Some content sections are missing")
        
        return {
            "title": title,
            "script": script,
            "hashtags": hashtags,
            "format": {
                "type": format_spec["type"],
                "duration": format_spec["duration"]
            }
        }