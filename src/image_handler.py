import os
from pathlib import Path
import base64
import time
import asyncio
from PIL import Image
from together import Together
import io

class ImageHandler:
    def __init__(self):
        self.together_client = Together()
        self.last_request_time = 0
        self.RATE_LIMIT_DELAY = 10  # 10 seconds between requests
        
        # Define video format specifications
        self.VIDEO_FORMATS = {
            "shorts": {
                "width": 1080,
                "height": 1920,
                "aspect_ratio": "9:16"
            },
            "normal": {
                "width": 1920,
                "height": 1080,
                "aspect_ratio": "16:9"
            }
        }
        
        self.DEFAULT_OUTPUT_DIR = Path("contents/images")
        self.current_format = "shorts"
        self.WIDTH = self.VIDEO_FORMATS["shorts"]["width"]
        self.HEIGHT = self.VIDEO_FORMATS["shorts"]["height"]

    async def generate_image(
        self,
        prompt: str,
        index: int,
        length: int,
        output_dir: str = None
    ) -> str:
        """
        Generate an image and save it to file
        
        Args:
            prompt: Image generation prompt
            index: Image index
            length: Total number of images
            output_dir: Optional output directory (defaults to contents/images)
        """
        try:
            # Rate limiting
            current_time = time.time()
            if current_time - self.last_request_time < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - (current_time - self.last_request_time))
            
            # Calculate dimensions based on format
            width_steps = 64  # Base step size
            height_steps = 64
            
            if self.current_format == "shorts":
                width = 9 * width_steps   # 576 pixels (9:16 ratio)
                height = 16 * height_steps # 1024 pixels
            else:
                width = 16 * width_steps  # 1024 pixels (16:9 ratio)
                height = 9 * height_steps  # 576 pixels
            
            print(f"Generating {self.current_format} format image {index + 1}/{length}")
            
            response = self.together_client.images.generate(
                prompt=prompt,
                model="black-forest-labs/FLUX.1-schnell-Free",
                width=width,
                height=height,
                steps=4,
                n=1,
                response_format="b64_json"
            )
            
            self.last_request_time = time.time()
            
            # Process and save the image
            if response and hasattr(response, 'data') and len(response.data) > 0:
                b64_json = response.data[0].b64_json
                image_bytes = base64.b64decode(b64_json)
                
                # Convert bytes to PIL Image for proper saving
                with Image.open(io.BytesIO(image_bytes)) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    # Resize to video dimensions if needed
                    if img.size != (self.WIDTH, self.HEIGHT):
                        img = img.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)
                    
                    # Use provided output directory or default
                    if not output_dir:
                        output_dir = self.DEFAULT_OUTPUT_DIR
                    output_dir = Path(output_dir)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    # Save to file
                    output_path = output_dir / f"frame_{index}.jpg"
                    img.save(str(output_path), "JPEG", quality=95)
                
                print(f"Successfully generated image {index + 1}")
                return str(output_path)
            else:
                print(f"Error: Invalid response format from Together AI")
                return None
            
        except Exception as e:
            print(f"Error generating image: {str(e)}")
            return None

    async def generate_images(self, prompts: list[str], output_dir: str = None) -> list[str]:
        """
        Generate all images and return their file paths
        
        Args:
            prompts: List of image generation prompts
            output_dir: Optional output directory (defaults to contents/images)
        """
        image_paths = []
        
        for i, prompt in enumerate(prompts):
            image_path = await self.generate_image(prompt, i, len(prompts), output_dir)
            if image_path:
                image_paths.append(image_path)
        
        return image_paths

    def set_format(self, format_type: str):
        """Set the video format (shorts or normal)"""
        if format_type in self.VIDEO_FORMATS:
            self.current_format = format_type
            self.WIDTH = self.VIDEO_FORMATS[format_type]["width"]
            self.HEIGHT = self.VIDEO_FORMATS[format_type]["height"]
