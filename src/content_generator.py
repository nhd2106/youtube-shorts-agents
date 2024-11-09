from typing import TypedDict
import os
from openai import AsyncOpenAI
from typing import Optional

class Content(TypedDict):
    script: str
    title: str
    hashtags: list[str]

class ContentGenerator:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def generate_content(self, idea: str) -> Content:
        try:
            # Create system prompt to define the format
            system_prompt = """You are a Vietnamese content creator specialized in creating YouTube Shorts scripts.
            You must always respond in the exact format:
            TITLE: [catchy Vietnamese title]
            SCRIPT: [Vietnamese script]
            HASHTAGS: [relevant hashtags]
            
            Follow these guidelines:
            1. Title should be catchy and in Vietnamese
            2. Script must: 
                - Be in Vietnamese
                - Start with "Xin chào các bạn!"
                - Be 45-60 seconds when read
                - Should be browsing the internet to find the most interesting and relevant information
                - Also browsing to get correct information
                - End with "Các bạn nghĩ sao về những điều này? Nếu thấy video này hay, đừng quên bấm like và đăng ký kênh nhé!"
                - In case user give you the link, you should browse the link and get the most interesting and relevant information
                - All numbers should be in text format
            3. Hashtags should be relevant, mix of Vietnamese and English"""
            
            # Make the API call
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # or "gpt-3.5-turbo" for lower cost
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Create a YouTube Short script about: {idea}"}
                ],
                temperature=0.7,
                
            )
            
            # Get the content
            content = response.choices[0].message.content
            print("\nDebug - Raw API Response:")
            print(content)
            
            # Parse and return the content
            return self._parse_content(content)
            
        except Exception as e:
            print(f"\nDebug - Error details: {str(e)}")
            raise

    def _parse_content(self, content: str) -> Content:
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
            "hashtags": hashtags
        }