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
            1. Title should be catchy and in Vietnamese
            2. Script must: 
                - Start with an irresistible hook in the first 3 seconds using ONE of these:
                    * Mind-blowing statistic that challenges common beliefs
                    * Controversial "hot take" that makes viewers stop scrolling
                    * "What if I told you..." followed by an unexpected revelation
                    * Personal story that hits emotional pain points
                    * Direct challenge to viewer: "You've been doing X wrong all along"
                    * Time-sensitive urgency: "In the next 60 seconds..."
                - In case user ask about history, you should answer with time and place if possible
                - In case user ask for a story, you should answer with meaningful story dont stop too fast  
                - In case user ask for facts, you should answer in 7-10 facts about the topic
                - Be in Vietnamese
                - Be {format_spec['script_length']} when read
                - Be {format_spec['style']}
                - Should be browsing the internet for accurate information
                - Structure: Attention-grabbing hook → Problem → Solution → Call to action
                - End with "Các bạn nghĩ sao về những điều này? Nếu thấy video này hữu ích, đừng ngại bấm like và đăng ký để ủng hộ kênh!"
            3. Hashtags should be relevant, mix of Vietnamese and English"""

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