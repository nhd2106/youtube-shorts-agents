from moviepy.editor import AudioFileClip, TextClip, CompositeVideoClip, ImageClip, ColorClip, vfx
from moviepy.config import change_settings
from pathlib import Path
from typing import Optional
import os
import re
import speech_recognition as sr
import openai
import asyncio
import time
from together import Together
from proglog import ProgressBarLogger
import math
from PIL import Image

class MyBarLogger(ProgressBarLogger):
    def __init__(self, progress_callback=None):
        super().__init__()
        self.progress_callback = progress_callback

    def callback(self, **changes):
        # Every time the logger is updated, this is called
        for (parameter, value) in changes.items():
            if parameter == 'frame' and self.progress_callback:
                total = self.bars['t'].max_value
                if total != 0:
                    percentage = (value / total) * 100
                    self.progress_callback('render', percentage)
        super().callback(**changes)

class VideoGenerator:
    def __init__(self):
        self.OUTPUT_DIR = Path("contents/video")
        self.WIDTH = 1080
        self.HEIGHT = 1920
        self.DURATION = None
        
        # Set ImageMagick binary path for MoviePy
        if os.path.exists('/opt/homebrew/bin/convert'):
            change_settings({"IMAGEMAGICK_BINARY": "/opt/homebrew/bin/convert"})
        elif os.path.exists('/usr/local/bin/convert'):
            change_settings({"IMAGEMAGICK_BINARY": "/usr/local/bin/convert"})

        self.together_client = Together()
        self.openai_client = openai.AsyncOpenAI()
        self.image_cache = {}
        self.last_request_time = 0
        self.RATE_LIMIT_DELAY = 10  # 10 seconds between requests

    def split_into_phrases(self, text: str) -> list[str]:
        """Split text into natural phrases using punctuation and length"""
        # Split by punctuation but keep the punctuation marks
        raw_phrases = re.split('([.,!?])', text)
        phrases = []
        current_phrase = ''
        
        for i in range(0, len(raw_phrases), 2):
            part = raw_phrases[i].strip()
            punctuation = raw_phrases[i + 1] if i + 1 < len(raw_phrases) else ''
            
            if part:
                current_phrase = part + punctuation
                phrases.append(current_phrase)
        
        return phrases

    def create_text_clip(self, text: str, start_time: float, duration: float) -> TextClip:
        """Create an animated text clip with enhanced effects"""
        # Create main text clip with improved styling
        text_clip = TextClip(
            text,
            font='Arial-Bold',
            fontsize=60,
            color='yellow',
            size=(self.WIDTH - 100, None),
            method='caption',
            align='center',
            stroke_color='black',
            stroke_width=2
        )
        
        # Create solid background
        bg = ColorClip(
            size=(text_clip.w + 40, text_clip.h + 40),
            color=(0, 0, 0)
        ).set_opacity(0.7)
        
        # Add glow effect without resize
        glow = text_clip.copy()
        glow = glow.set_opacity(0.3)
        
        # Calculate center position
        center_pos = ('center', 'center')
        
        # Create glow positions using lambda functions for offset
        def offset_position(x_offset=0, y_offset=0):
            return lambda t: (
                'center',
                'center' if y_offset == 0 else self.HEIGHT//2 + y_offset
            )
        
        # Composite clips with layered glow effect
        final_clip = CompositeVideoClip([
            bg.set_position(center_pos),
            glow.set_position(offset_position(y_offset=-1)),  # Up
            glow.set_position(offset_position(y_offset=1)),   # Down
            glow.set_position(offset_position()),             # Center
            text_clip.set_position(center_pos)
        ])
        
        # Add animations
        final_clip = self._add_text_animations(
            final_clip, 
            start_time, 
            duration,
            animation_style='random'
        )
        
        return final_clip

    def _add_text_animations(self, clip, start_time, duration, animation_style='random'):
        """Add various animation styles to text clips"""
        import random
        
        styles = ['slide', 'fade']
        if animation_style == 'random':
            animation_style = random.choice(styles)
            
        # Base timing setup
        clip = clip.set_start(start_time).set_duration(duration)
        
        # Animation parameters
        fade_duration = 0.3
        slide_distance = 50
        
        if animation_style == 'slide':
            # Slide in from right, out to left
            clip = clip.set_position(
                lambda t: (
                    'center' if fade_duration < t < duration - fade_duration
                    else ('center', self.HEIGHT * 2/3 + slide_distance * (1 - t/fade_duration))
                    if t <= fade_duration
                    else ('center', self.HEIGHT * 2/3 + slide_distance * ((t - (duration - fade_duration))/fade_duration))
                )
            )
            
        elif animation_style == 'fade':
            # Fade in/out
            clip = clip.fx(
                vfx.fadein, fade_duration
            ).fx(
                vfx.fadeout, fade_duration
            )
            
        # Add common effects
        clip = clip.crossfadein(fade_duration)
        clip = clip.crossfadeout(fade_duration)
        
        # Remove bouncing animation, keep only subtle floating motion
        float_amount = 5
        base_y = self.HEIGHT * 2/3
        clip = clip.set_position(
            lambda t: ('center', base_y)
        )
        
        return clip

    async def generate_prompts_with_openai(self, script: str) -> list[str]:
        """Generate image prompts using OpenAI"""
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a professional cinematographer creating video prompts. 
                        Create prompts for black-forest-labs/FLUX.1-schnell-Free model. Your task is to:
                        1. Create 6-7 cinematic, photorealistic prompts
                        2. Each prompt MUST include camera angle and cinematography techniques
                        3. Use these essential cinematography terms in your prompts:
                           - Camera angles: Low angle, High angle, Overhead, FPV (First Person View), Wide angle
                           - Shot types: Close up, Medium shot, Wide shot, Macro
                           - Camera movement: Tracking shot, Dolly zoom, Hand held, Steady cam
                           - Lighting: Natural lighting, Diffused lighting, Rim lighting, Lens flare
                           - Time of day: Golden hour, Blue hour, Midday, Dusk
                           - Weather: Overcast, Clear sky, Dramatic clouds
                        
                        Example good prompts:
                        "Low angle shot of SpaceX rocket launch, golden hour lighting, lens flare, dramatic clouds"
                        "Wide angle tracking shot of Tesla factory, diffused industrial lighting, steady cam movement"
                        "Close up portrait of Elon Musk, shallow depth of field, natural window lighting, office setting"
                        """
                    },
                    {
                        "role": "user",
                        "content": f"""Create 6-7 cinematic prompts for this script: 
                        {script}
                        
                        Requirements:
                        - MUST include at least one camera angle/movement term in each prompt
                        - MUST include lighting and atmosphere descriptions
                        - Focus on photorealistic quality
                        - Incorporate relevant subject matter from the script
                        - Each prompt should be under 150 characters
                        - Include time of day or weather elements when relevant
                        - No timestamps or descriptions, just the prompts
                        """
                    }
                ]
            )
            
            # Parse prompts from response
            prompts_text = response.choices[0].message.content
            prompts = []
            
            # Clean and filter prompts
            for line in prompts_text.split('\n'):
                line = line.strip()
                # Remove numbering, timestamps, or other prefixes
                line = re.sub(r'^[\d\-\.\s]*|^\*+\s*|^prompt:?\s*', '', line, flags=re.IGNORECASE)
                
                if line and len(line) > 10:  # Ensure meaningful content
                    prompts.append(line)
            
            # Ensure we have at least one prompt
            if not prompts:
                prompts = [
                    "Abstract flowing gradient of deep blues and purples with soft light waves",
                    "Gentle swirling patterns of warm colors with subtle motion",
                    "Dynamic geometric shapes floating in a misty atmosphere",
                    "Ethereal light patterns dancing through dark space",
                    "Smooth transitions of cool tones with floating particles"
                ]
            
            print("🎨 Generated prompts:")
            for i, prompt in enumerate(prompts, 1):
                print(f"{i}. {prompt}")
            
            return prompts

        except Exception as e:
            print(f"Error generating prompts: {str(e)}")
            # Return default prompts if OpenAI fails
            return [
                "Abstract flowing gradient of deep blues and purples with soft light waves",
                "Gentle swirling patterns of warm colors with subtle motion",
                "Dynamic geometric shapes floating in a misty atmosphere",
                "Ethereal light patterns dancing through dark space",
                "Smooth transitions of cool tones with floating particles"
            ]

    async def generate_background_images(self, prompts: list[str]) -> dict:
        """Generate background images with rate limiting"""
        background_images = {}
        
        for i, prompt in enumerate(prompts):
            if prompt in self.image_cache:
                background_images[i] = self.image_cache[prompt]
                continue

            # Rate limiting
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.RATE_LIMIT_DELAY:
                await asyncio.sleep(self.RATE_LIMIT_DELAY - time_since_last_request)

            try:
                print(f"Generating image {i + 1}/{len(prompts)} with prompt: {prompt[:100]}...")  # Debug log
                response = self.together_client.images.generate(
                    prompt=prompt,
                    model="black-forest-labs/FLUX.1-schnell-Free",
                    width=9 * 64,
                    height=16 * 64,
                    steps=4,
                    n=1,
                    response_format="b64_json"
                )
                
                # Convert and store image
                image_array = self._process_image_response(response)
                background_images[i] = image_array
                self.image_cache[prompt] = image_array
                self.last_request_time = time.time()
                print(f"Successfully generated image {i + 1}")  # Success log
                
            except Exception as e:
                print(f"Error generating image {i + 1}:")  # Detailed error logging
                print(f"Prompt: {prompt}")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                print("Full traceback:")
                import traceback
                traceback.print_exc()
                continue

        return background_images

    def create_title_clip(self, text: str, duration: float) -> TextClip:
        """Create an enhanced title clip with dynamic effects"""
        # Create main title with improved styling
        text_clip = TextClip(
            text,
            font='Arial-Bold',
            fontsize=90,
            color='yellow',
            size=(self.WIDTH - 100, None),
            method='caption',
            align='center',
            stroke_color='yellow',
            stroke_width=3
        )
        
        # Create solid color background
        bg = ColorClip(
            size=(text_clip.w + 60, text_clip.h + 60),
            color=(0, 0, 50)
        ).set_opacity(0.8)
        
        # Add glow effect without resize
        glow = text_clip.copy()
        glow = glow.set_opacity(0.4)
        
        # Calculate center position
        center_pos = ('center', 'center')
        
        # Create glow positions using lambda functions for offset
        def offset_position(x_offset=0, y_offset=0):
            return lambda t: (
                'center',
                'center' if y_offset == 0 else self.HEIGHT//2 + y_offset
            )
        
        # Composite with animations - layer multiple glows with different offsets
        final_clip = CompositeVideoClip([
            bg.set_position(center_pos),
            glow.set_position(offset_position(y_offset=-2)),  # Up
            glow.set_position(offset_position(y_offset=2)),   # Down
            glow.set_position(offset_position()),             # Center
            text_clip.set_position(center_pos)
        ])
        
        # Add title-specific animations
        final_clip = final_clip.set_duration(duration)
        final_clip = final_clip.fadein(1.0)
        final_clip = final_clip.fadeout(1.0)
        
        # Add floating effect
        float_amount = 8
        final_clip = final_clip.set_position(
            lambda t: ('center', self.HEIGHT * 1/5 + float_amount * math.sin(2 * math.pi * t / 4))
        )
        
        return final_clip

    async def generate_video(
        self, 
        audio_path: str, 
        content: dict, 
        filename: str, 
        progress_callback: callable = None
    ) -> str:
        """Generate video with progress updates"""
        try:
            # Add debug logging for input validation
            print(f"Debug: Starting generate_video with filename: {filename}")
            print(f"Debug: Audio path exists: {os.path.exists(audio_path)}")
            print(f"Debug: Content script length: {len(content.get('script', ''))}")
            
            # Ensure output directory exists
            self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            video_path = self.OUTPUT_DIR / f"{filename}.mp4"
            print(f"Debug: Video will be saved to: {video_path}")
            
            # Load audio and get duration
            if not os.path.exists(audio_path):
                raise FileNotFoundError(f"Audio file not found at {audio_path}")
                
            print("Loading audio file...")
            audio = AudioFileClip(audio_path)
            self.DURATION = audio.duration
            print(f"Debug: Audio duration: {self.DURATION}")
            
            if progress_callback:
                progress_callback('compose', 0)
            
            # Generate prompts using OpenAI
            print("Generating prompts...")  # Debug log
            prompts = await self.generate_prompts_with_openai(content['script'])
            if not prompts:
                raise ValueError("No prompts generated from OpenAI")
                
            if progress_callback:
                progress_callback('compose', 10)
                
            # Generate background images
            print("Generating background images...")  # Debug log
            background_images = await self.generate_background_images(prompts)
            if not background_images:
                raise ValueError("Failed to generate any background images")
            
            # Create background clips
            print("Creating background clips...")  # Debug log
            segment_duration = self.DURATION / max(len(prompts), 1)
            background_clips = []
            transition_duration = 1.0  # 1 second transition
            
            for i, image_array in background_images.items():
                if image_array is None:
                    print(f"Warning: Image array is None for prompt {i}")
                    continue
                    
                start_time = i * segment_duration
                bg_clip = ImageClip(image_array)
                
                # Set initial duration before applying effects
                if i < len(background_images) - 1:  # Not the last clip
                    clip_duration = segment_duration + transition_duration
                else:  # Last clip
                    clip_duration = segment_duration
                
                bg_clip = bg_clip.set_duration(clip_duration)
                
                # Add crossfade transitions after setting duration
                if i > 0:  # Not the first clip
                    bg_clip = bg_clip.set_start(start_time - transition_duration)
                    bg_clip = bg_clip.crossfadein(transition_duration)
                else:
                    bg_clip = bg_clip.set_start(start_time)
                
                background_clips.append(bg_clip)
            
            if not background_clips:
                raise ValueError("No background clips were generated")
            
            # Create title clip (add after background clips creation)
            print("Creating title clip...")
            title_clip = self.create_title_clip(
                content.get('title', 'Untitled'),
                self.DURATION  # Show title for full duration
            )
            
            # Create text clips with improved timing
            print("Creating text clips...")  # Debug log
            phrases = self.split_into_phrases(content['script'])
            text_clips = []
            
            # Calculate total duration and adjust timing
            total_chars = sum(len(phrase) for phrase in phrases)
            # Adjust these values to fine-tune the timing
            base_duration = 0.25  # Base duration per character
            min_duration = 1.5    # Minimum duration for very short phrases
            
            current_time = 0
            remaining_duration = self.DURATION
            
            for i, phrase in enumerate(phrases):
                # Calculate phrase duration based on character count
                char_count = len(phrase)
                if i == len(phrases) - 1:
                    # Last phrase uses remaining duration
                    phrase_duration = remaining_duration
                else:
                    # Calculate proportional duration
                    phrase_duration = max(
                        min_duration,
                        (char_count / total_chars) * self.DURATION
                    )
                    remaining_duration -= phrase_duration
                
                text_clip = self.create_text_clip(
                    phrase,
                    start_time=current_time,
                    duration=phrase_duration
                )
                
                text_clips.append(text_clip)
                current_time += phrase_duration

            if progress_callback:
                progress_callback('compose', 60)

            # Combine everything
            print("Compositing final video...")  # Debug log
            final_video = CompositeVideoClip(
                background_clips + [title_clip] + text_clips,  # Add title_clip to the composition
                size=(self.WIDTH, self.HEIGHT)
            ).set_audio(audio)
            
            if progress_callback:
                progress_callback('compose', 100)
                progress_callback('render', 0)

            # Add more detailed error checking before writing video
            if not background_clips:
                raise ValueError("No background clips were generated")
            
            if not text_clips:
                raise ValueError("No text clips were generated")
            
            # Add debug logging before writing
            print(f"Debug: About to write video to {video_path}")
            print(f"Debug: Video duration: {final_video.duration}")
            print(f"Debug: Video size: {final_video.size}")
            
            # Create custom logger
            logger = MyBarLogger(progress_callback) if progress_callback else None
            
            # Write video file with explicit error handling
            try:
                final_video.write_videofile(
                    str(video_path),
                    fps=30,
                    codec='libx264',
                    audio_codec='aac',
                    threads=4,
                    preset='ultrafast',
                    logger=logger
                )
            except Exception as write_error:
                print(f"Error writing video file: {str(write_error)}")
                raise

            # Verify file was created
            if not video_path.exists():
                raise ValueError(f"Video file was not created at {video_path}")
                
            print(f"Debug: Video successfully created at {video_path}")
            
            # Clean up
            final_video.close()
            audio.close()
            
            if progress_callback:
                progress_callback('export', 100)

            return str(video_path)
            
        except Exception as e:
            print(f"Error in generate_video:")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def get_word_timings(self, audio_path: str) -> list[dict]:
        """Get precise word timings using speech recognition"""
        r = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = r.record(source)
            result = r.recognize_google(audio, show_all=True)
            return result['result'][0]['alternative'][0]['timestamps']

    def animate_text(self, txt_clip):
        """Add more complex text animations"""
        return txt_clip.fx(
            vfx.slide_in, duration=0.5, side='right'
        ).fx(
            vfx.slide_out, duration=0.5, side='left'
        )

    def _process_image_response(self, response):
        """Helper method to process image response"""
        import base64
        import io
        from PIL import Image
        import numpy as np
        
        try:
            image_data = base64.b64decode(response.data[0].b64_json)
            image = Image.open(io.BytesIO(image_data))
            
            # Resize using new Pillow syntax
            if image.size != (self.WIDTH, self.HEIGHT):
                image = image.resize(
                    (self.WIDTH, self.HEIGHT),
                    Image.Resampling.LANCZOS  # Use LANCZOS instead of ANTIALIAS
                )
            
            return np.array(image)
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            # Return a default colored background
            return np.full((self.HEIGHT, self.WIDTH, 3), [25, 25, 25], dtype=np.uint8)

    def validate_dependencies(self) -> None:
        """Validate that all required dependencies are available"""
        try:
            # Check for required Python packages
            import moviepy.editor
            import PIL
            
            # Check for required directories
            required_dirs = ['contents/video', 'contents/audio', 'contents/temp']
            for dir_path in required_dirs:
                os.makedirs(dir_path, exist_ok=True)
                
            # Check write permissions
            for dir_path in required_dirs:
                test_file = os.path.join(dir_path, '.test')
                try:
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                except Exception as e:
                    raise PermissionError(f"Cannot write to {dir_path}: {str(e)}")
                    
        except ImportError as e:
            raise RuntimeError(f"Missing required dependency: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Validation failed: {str(e)}")