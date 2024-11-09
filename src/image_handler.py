from typing import List
import os
from openai import OpenAI

class ImageHandler:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def generate_images(self, script: str, num_images: int = 3) -> List[str]:
        prompt = f"Create an engaging image for a YouTube Short with this script: {script}"
        
        response = await self.client.images.create(
            model="dall-e-3",
            prompt=prompt,
            size="1080x1920",  # Vertical format for Shorts
            quality="standard",
            n=num_images
        )
        
        return [image.url for image in response.data] 