from pathlib import Path
import base64
import time
import asyncio
from PIL import Image
from together import Together
import io
import os
import uuid
import requests
from typing import List, Optional

class ImageHandler:
    def __init__(self):
        self.together_client = None
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
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def _init_together_client(self, api_keys: dict):
        """Initialize Together AI client with API key"""
        if not api_keys or not api_keys.get('together'):
            raise ValueError("Together AI API key is required for image generation")
        try:
            client = Together(api_key=api_keys['together'])
            # Test if client is properly initialized
            if not hasattr(client, 'images'):
                raise ValueError("Together client not properly initialized")
            self.together_client = client
            print("Together AI client initialized successfully")
        except Exception as e:
            print(f"Error initializing Together client: {str(e)}")
            self.together_client = None
            raise

    async def generate_image(
        self,
        prompt: str,
        index: int,
        length: int,
        output_dir: str = None,
        api_keys: dict = None
    ) -> str:
        """Generate an image and save it to file"""
        # Initialize client if not already initialized
        if not self.together_client:
            self._init_together_client(api_keys)
        
        # Double check client is properly initialized
        if not self.together_client or not hasattr(self.together_client, 'images'):
            raise ValueError("Together client not properly initialized")

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
                
                try:
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
                    
                    # Get base64 data directly from response
                    if response and hasattr(response, 'data') and len(response.data) > 0:
                        b64_json = response.data[0].b64_json
                    else:
                        print("No valid response data received")
                        return None
                    
                    # Process and save the image
                    try:
                        image_data = base64.b64decode(b64_json)
                        image = Image.open(io.BytesIO(image_data))
                        
                        # Convert to RGB if necessary
                        if image.mode != 'RGB':
                            image = image.convert('RGB')
                        
                        # Resize to match video dimensions
                        image = self._resize_and_crop(image)
                        
                        # Generate output path
                        if not output_dir:
                            output_dir = str(self.DEFAULT_OUTPUT_DIR)
                        os.makedirs(output_dir, exist_ok=True)
                        
                        output_path = os.path.join(output_dir, f"generated_image_{index}.jpg")
                        
                        # Save the image
                        image.save(output_path, 'JPEG', quality=95)
                        print(f"Saved generated image to: {output_path}")
                        
                        return output_path
                        
                    except Exception as e:
                        print(f"Error processing image data: {str(e)}")
                        return None
                    
                except Exception as api_error:
                    print(f"API Error: {str(api_error)}")
                    return None
                
            except Exception as e:
                print(f"Error generating image: {str(e)}")
                return None

    async def generate_background_images(
        self,
        prompts: List[str],
        request_id: str,
        output_dir: str = None,
        api_keys: dict = None,
        image_urls: List[str] = None
    ) -> List[str]:
        """Generate background images using Together AI or download from URLs"""
        try:
            if not output_dir:
                output_dir = os.path.join("contents", request_id, "images")
            os.makedirs(output_dir, exist_ok=True)
            
            image_paths = []
            
            # If we have image URLs, try to download them first
            if image_urls:
                print(f"Found {len(image_urls)} images from URLs, attempting to download...")
                download_tasks = [
                    self.download_and_process_image(url, output_dir=output_dir)
                    for url in image_urls
                ]
                download_results = await asyncio.gather(*download_tasks)
                image_paths = [path for path in download_results if path]
                print(f"Successfully downloaded {len(image_paths)} images from URLs")
                
                # If we have enough images from URLs, return them
                required_images = 9 if self.current_format == 'shorts' else 18
                if len(image_paths) >= required_images:
                    print(f"Got enough images from URLs ({len(image_paths)}), skipping AI generation")
                    return image_paths
                
                print(f"Not enough images from URLs ({len(image_paths)}), generating {required_images - len(image_paths)} more...")
                # Adjust number of prompts based on remaining needed images
                prompts = prompts[:required_images - len(image_paths)]
            
            # Only generate AI images if we need more
            if prompts:
                if not api_keys:
                    raise ValueError("API keys are required for image generation")
                
                self._init_together_client(api_keys)
                
                # Process prompts in batches
                for i in range(0, len(prompts), self.BATCH_SIZE):
                    batch_prompts = prompts[i:i + self.BATCH_SIZE]
                    batch_tasks = [
                        self.generate_image(
                            prompt,
                            i + idx,
                            len(prompts),
                            output_dir,
                            api_keys=api_keys
                        )
                        for idx, prompt in enumerate(batch_prompts)
                    ]
                    
                    # Process batch in parallel
                    batch_results = await asyncio.gather(*batch_tasks)
                    image_paths.extend([path for path in batch_results if path])
            
            return image_paths
            
        except Exception as e:
            print(f"Error in image generation: {str(e)}")
            return []

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

    async def download_and_process_image(self, url: str, output_dir: str = None, output_path: str = None) -> Optional[str]:
        """Download and process an image from a URL"""
        try:
            # Handle output path
            if output_path is None and output_dir is not None:
                # Generate unique filename
                filename = f"{uuid.uuid4()}.jpg"
                output_path = os.path.join(output_dir, filename)
            elif output_path is None and output_dir is None:
                raise ValueError("Either output_dir or output_path must be provided")

            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Create a session with retries
            session = requests.Session()
            retries = requests.adapters.Retry(total=3, backoff_factor=0.5)
            adapter = requests.adapters.HTTPAdapter(max_retries=retries)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            
            # Set headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive'
            }
            
            # Download the image
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Process image with PIL
            image = Image.open(io.BytesIO(response.content))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Get original dimensions for logging
            original_size = image.size
            
            # Check if image is too small
            if original_size[0] < 300 or original_size[1] < 300:
                print(f"Image too small: {original_size}")
                return None
            
            # Resize and crop to match video dimensions
            resized_image = self._resize_and_crop(image)
            
            # Save processed image
            resized_image.save(output_path, 'JPEG', quality=95)
            
            print(f"Successfully processed image: {url}")
            print(f"Original size: {original_size}, Resized to: {resized_image.size}")
            return output_path
            
        except Exception as e:
            print(f"Error processing image from {url}: {str(e)}")
            return None

    def _resize_and_crop(self, image: Image.Image) -> Image.Image:
        """Resize and crop image to match video dimensions while maintaining aspect ratio"""
        # Calculate target aspect ratio
        target_ratio = self.WIDTH / self.HEIGHT
        
        # Get current image dimensions
        width, height = image.size
        current_ratio = width / height
        
        if current_ratio > target_ratio:
            # Image is wider than needed
            new_width = int(height * target_ratio)
            left = (width - new_width) // 2
            image = image.crop((left, 0, left + new_width, height))
        else:
            # Image is taller than needed
            new_height = int(width / target_ratio)
            top = (height - new_height) // 2
            image = image.crop((0, top, width, top + new_height))
        
        # Resize to target dimensions using Lanczos resampling
        return image.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)
