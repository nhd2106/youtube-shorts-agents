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
                    "style": "energetic and engaging",
                    "word_count": "200-250 words"
                },
                "normal": {
                    "type": "normal",
                    "duration": "flexible",
                    "script_length": "8-10 minutes",
                    "style": "detailed and comprehensive",
                    "word_count": "1200-1500 words"
                }
            }

            if video_format not in format_specs:
                raise ValueError(f"Invalid video format. Choose from: {list(format_specs.keys())}")

            format_spec = format_specs[video_format]

            # Update system prompt based on video format
            system_prompt = f'''You are a creative content specialist focused on creating engaging {video_format} videos.
You must respond in this exact format:
TITLE: [attention-grabbing title]
SCRIPT: [engaging script]
HASHTAGS: [relevant hashtags]

Guidelines for content creation:
1. Title Creation:
    - Ensure the title language matches the user input
    - Craft an attention-grabbing, unique title that sparks curiosity
    - Use relevant keywords for better discoverability
    - Keep it clear, concise, and compelling
    - Avoid clickbait - ensure the title accurately reflects content

2. Script rules:
    - Content Type Guidelines:
        • Historical: Include precise dates, locations, and detailed context
        • Narrative: Ensure complete, satisfying story arcs with character development
        • Factual: Present {format_spec["type"] == "shorts" and "7-10" or "15-20"} verified, engaging facts
        • Tutorial: Provide clear, step-by-step instructions with detailed explanations
        • Opinion: Balance viewpoints with evidence and expert citations
    - Content Requirements:
        • Consistently match the input language
        • Focus solely on the requested topic
        • Target length: {format_spec["word_count"]} for a {format_spec["script_length"]} video
        • Keep the tone {format_spec["style"]}
        • For normal format: Include detailed examples, case studies, or real-world applications
        • For shorts: Keep it concise and immediately engaging
        • Conclude with: in English "If you found this helpful, like and subscribe for more!"  and in Vietnamese "Nếu bạn thấy hay, đừng quên bấm like và đăng ký để ủng hộ kênh" 
    - Storytelling Framework - Select ONE:
        • Hero's Journey: Challenge → Struggle → Triumph
        • 7-Second Hook: Grab attention in the first 7 seconds
        • Problem-Solution-Benefit Structure
        • 5-Why Analysis: Deep dive into root causes
        • Dual-Perspective Story: Before/After format
        • 10-Second Engagement Rule
        • Rhythmic/Rhyming Pattern for memorability
    * Remember: Language must match with the user input language

3. Hashtag Strategy:
    - Blend English and topic-specific hashtags
    - Include trending, relevant tags
    - Ensure hashtag relevance to content
    - Optimal mix: 60% topic-specific, 40% general engagement

4. Quality Standards:
    - Prioritize accuracy and current information
    - Maintain educational or entertainment value
    - Focus on audience engagement and value delivery
    - Keep content concise and impactful
    - Avoid filler content or unnecessary details
    - For normal format: Include supporting details, examples, and deeper analysis
    - For shorts: Focus on key points and immediate value

Note: Exclude emojis, icons, or special characters from the script content.'''

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