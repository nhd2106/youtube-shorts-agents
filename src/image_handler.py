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
        self.BATCH_SIZE = 3  # Process images in batches of 3
        
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
        
        # Don't set default format in __init__, wait for explicit set_format call
        self.current_format = None
        self.WIDTH = None
        self.HEIGHT = None
        
        # Create image processing semaphore
        self.semaphore = asyncio.Semaphore(3)  # Limit concurrent API calls

    async def generate_image(
        self,
        prompt: str,
        index: int,
        length: int,
        output_dir: str = None
    ) -> str:
        """Generate an image and save it to file"""
        async with self.semaphore:  # Control concurrent API calls
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
                    return await self._process_and_save_image(
                        response.data[0].b64_json,
                        index,
                        output_dir
                    )
                else:
                    print(f"Error: Invalid response format from Together AI")
                    return None
                
            except Exception as e:
                print(f"Error generating image: {str(e)}")
                return None

    async def _process_and_save_image(self, b64_json: str, index: int, output_dir: str = None) -> str:
        """Process and save image from base64 data"""
        try:
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
            
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return None

    async def generate_images(self, prompts: list[str], output_dir: str = None) -> list[str]:
        """Generate all images in parallel batches"""
        image_paths = []
        
        # Process prompts in batches
        for i in range(0, len(prompts), self.BATCH_SIZE):
            batch_prompts = prompts[i:i + self.BATCH_SIZE]
            batch_tasks = [
                self.generate_image(
                    prompt,
                    i + idx,
                    len(prompts),
                    output_dir
                )
                for idx, prompt in enumerate(batch_prompts)
            ]
            
            # Process batch in parallel
            batch_results = await asyncio.gather(*batch_tasks)
            image_paths.extend([path for path in batch_results if path])
        
        return image_paths

    def set_format(self, format_type: str):
        """Set the video format (shorts or normal)"""
        if format_type not in self.VIDEO_FORMATS:
            raise ValueError(f"Invalid format type. Choose from: {list(self.VIDEO_FORMATS.keys())}")
        
        if self.current_format != format_type:  # Only update if format is different
            self.current_format = format_type
            self.WIDTH = self.VIDEO_FORMATS[format_type]["width"]
            self.HEIGHT = self.VIDEO_FORMATS[format_type]["height"]
            print(f"Image format set to {format_type} with dimensions {self.WIDTH}x{self.HEIGHT}")
        
        if self.WIDTH is None or self.HEIGHT is None:
            raise ValueError("Format must be set before generating images")
