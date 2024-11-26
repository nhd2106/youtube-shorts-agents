import os
import json
import math
import asyncio
import traceback
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
from moviepy.editor import *
from moviepy.video.tools.subtitles import SubtitlesClip
from moviepy.video.VideoClip import ColorClip, TextClip

from moviepy.editor import AudioFileClip, TextClip, CompositeVideoClip, ImageClip, ColorClip, vfx, VideoClip, VideoFileClip
from moviepy.config import change_settings
import re
import speech_recognition as sr
import openai
import time
from together import Together
from proglog import ProgressBarLogger
from difflib import SequenceMatcher
import tempfile
import vosk
import soundfile as sf
import whisper
import torch
from pydub import AudioSegment
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
import edge_tts
import librosa
import scipy.signal
import base64
import io

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
        
        self.DEFAULT_VIDEO_DIR = Path("contents/video")
        self.DEFAULT_THUMBNAIL_DIR = Path("contents/thumbnail")
        self.DEFAULT_TEMP_DIR = Path("contents/temp")
        
        # Don't set default format in __init__, wait for explicit set_format call
        self.current_format = None
        self.WIDTH = None
        self.HEIGHT = None
        
        # Set ImageMagick binary path for MoviePy
        if os.path.exists('/opt/homebrew/bin/convert'):
            change_settings({"IMAGEMAGICK_BINARY": "/opt/homebrew/bin/convert"})
        elif os.path.exists('/usr/local/bin/convert'):
            change_settings({"IMAGEMAGICK_BINARY": "/usr/local/bin/convert"})

        # Patch MoviePy's resize function to use Lanczos
        self._patch_moviepy_resize()

        # Ensure output directories exist
        os.makedirs(self.DEFAULT_VIDEO_DIR, exist_ok=True)
        os.makedirs(self.DEFAULT_THUMBNAIL_DIR, exist_ok=True)
        os.makedirs(self.DEFAULT_TEMP_DIR, exist_ok=True)

    def _patch_moviepy_resize(self):
        """Patch MoviePy's resize function to use Lanczos instead of ANTIALIAS"""
        from moviepy.video.fx.resize import resize
        from functools import wraps

        @wraps(resize)
        def new_resize(clip, newsize=None, height=None, width=None, apply_to_mask=True):
            if newsize is not None:
                w, h = newsize
            elif height is not None:
                w = int(clip.w * height / clip.h)
                h = height
            elif width is not None:
                h = int(clip.h * width / clip.w)
                w = width
            else:
                return clip

            def transform_frame(get_frame, t):
                frame = get_frame(t)
                if frame.shape[0:2] == (h, w):
                    return frame
                resized = np.array(Image.fromarray(frame).resize((w, h), Image.Resampling.LANCZOS))
                return resized

            new_clip = clip.transform(transform_frame, apply_to_mask=apply_to_mask)
            new_clip.w = w
            new_clip.h = h
            return new_clip

        # Patch the resize function
        import moviepy.video.fx.resize
        moviepy.video.fx.resize.resize = new_resize

    def split_into_phrases(self, text: str) -> list[str]:
        """Split text into natural phrases using punctuation"""
        # Split on punctuation but keep the punctuation marks
        import re
        
        # Define punctuation pattern
        pattern = r'([.!?,;:])'
        
        # Split text into sentences first
        sentences = re.split(pattern, text)
        
        # Clean up and combine punctuation with phrases
        phrases = []
        current_phrase = ""
        
        for item in sentences:
            if not item.strip():
                continue
            
            if re.match(pattern, item):
                # This is punctuation, add it to current phrase
                current_phrase += item
                phrases.append(current_phrase.strip())
                current_phrase = ""
            else:
                # This is text, start new phrase
                if current_phrase:
                    phrases.append(current_phrase.strip())
                current_phrase = item
        
        # Add any remaining phrase
        if current_phrase:
            phrases.append(current_phrase.strip())
        
        # Filter out empty phrases and normalize whitespace
        phrases = [' '.join(phrase.split()) for phrase in phrases if phrase.strip()]
        
        return phrases

    def create_text_clip(self, text: str, start_time: float, duration: float, is_silence: bool = False) -> TextClip:
        """Create text clip with karaoke effect"""
        try:
            if is_silence or not text:
                return None

            # Font settings
            fontsize = 72 if self.current_format == "shorts" else 60
            
            # Create the main text clip
            txt_clip = TextClip(
                text,
                font='Arial-Bold',
                fontsize=fontsize,
                color='yellow',  # Changed to yellow
                stroke_color='black',
                stroke_width=2,
                size=(self.WIDTH * 0.9, None),
                method='caption',
                align='center'
            )
            
            # Create background for text with padding
            padding = 20  # Pixels of padding around text
            bg_width = txt_clip.w + (padding * 2)
            bg_height = txt_clip.h + (padding * 2)
            
            # Create background clip with opacity
            bg_clip = ColorClip(
                size=(bg_width, bg_height),
                color=(0, 0, 0)
            ).set_opacity(0.7)
            
            # Compose text and background
            txt_clip = txt_clip.set_position((padding, padding))  # Center text in background
            composed_clip = CompositeVideoClip(
                [bg_clip, txt_clip],
                size=(bg_width, bg_height)
            )
            
            # Position at the bottom with padding
            bottom_padding = self.HEIGHT * 0.15  # 15% from bottom
            composed_clip = composed_clip.set_position(('center', self.HEIGHT - bottom_padding - bg_height))
            
            # Set timing
            composed_clip = composed_clip.set_start(start_time)
            composed_clip = composed_clip.set_duration(duration)
            
            # Add fade effects
            fade_duration = min(0.3, duration * 0.15)  # 15% of duration or 0.3s, whichever is shorter
            composed_clip = composed_clip.crossfadein(fade_duration)
            composed_clip = composed_clip.crossfadeout(fade_duration)
            
            return composed_clip
            
        except Exception as e:
            print(f"Error creating text clip: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _apply_random_transitions(self, clip, duration):
        """Apply random transitions to a clip"""
        import random
        from moviepy.video.VideoClip import VideoClip
        
        def ease_in_out(t):
            t = max(0, min(1, t/duration))
            return t * t * (3 - 2 * t)
        
        # Define possible effects
        effects = [
            # No movement
            {
                'name': 'static',
                'transform': lambda t: {
                    'scale': 1.0,
                    'pos_x': 0,
                    'pos_y': 0,
                    'needs_resize': False
                }
            },
            # Zoom in
            {
                'name': 'zoom_in',
                'transform': lambda t: {
                    'scale': 1.0 + (0.15 * ease_in_out(t)),
                    'pos_x': 0,
                    'pos_y': 0,
                    'needs_resize': True
                }
            },
            # Zoom out
            {
                'name': 'zoom_out',
                'transform': lambda t: {
                    'scale': 1.15 - (0.15 * ease_in_out(t)),
                    'pos_x': 0,
                    'pos_y': 0,
                    'needs_resize': True
                }
            },
            # Pan right
            {
                'name': 'pan_right',
                'transform': lambda t: {
                    'scale': 1.0,
                    'pos_x': -clip.w * 0.1 * ease_in_out(t),
                    'pos_y': 0,
                    'needs_resize': False
                }
            },
            # Pan left
            {
                'name': 'pan_left',
                'transform': lambda t: {
                    'scale': 1.0,
                    'pos_x': clip.w * 0.1 * ease_in_out(t),
                    'pos_y': 0,
                    'needs_resize': False
                }
            }
        ]
        
        # Select random effect
        effect = random.choice(effects)
        print(f"Applying {effect['name']} effect")
        
        def make_frame(t):
            frame = clip.get_frame(t)
            params = effect['transform'](t)
            
            # If no transformation needed
            if params['scale'] == 1.0 and params['pos_x'] == 0 and not params['needs_resize']:
                return frame
            
            img = Image.fromarray(frame)
            
            # Handle zoom only if needed
            if params['needs_resize']:
                new_w = int(clip.w * params['scale'])
                new_h = int(clip.h * params['scale'])
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # Center the zoomed image
                x1 = (new_w - clip.w) // 2
                y1 = (new_h - clip.h) // 2
            else:
                x1 = 0
                y1 = 0
            
            # Apply pan offset
            x1 += int(params['pos_x'])
            y1 += int(params['pos_y'])
            x2 = x1 + clip.w
            y2 = y1 + clip.h
            
            # Ensure boundaries
            if params['needs_resize']:
                x1 = max(0, min(x1, new_w - clip.w))
                y1 = max(0, min(y1, new_h - clip.h))
                x2 = min(new_w, x1 + clip.w)
                y2 = min(new_h, y1 + clip.h)
            else:
                x1 = max(0, min(x1, clip.w))
                y1 = max(0, min(y1, clip.h))
                x2 = min(clip.w, x1 + clip.w)
                y2 = min(clip.h, y1 + clip.h)
            
            img = img.crop((x1, y1, x2, y2))
            return np.array(img)
        
        new_clip = VideoClip(make_frame, duration=duration)
        new_clip = new_clip.set_duration(duration)
        new_clip = new_clip.fadein(duration * 0.05)
        new_clip = new_clip.fadeout(duration * 0.05)
        
        return new_clip

    def _create_background_clips(self, image_paths: list[str], durations: list[float]):
        """Create video clips from image paths with random transitions"""
        if not image_paths:
            raise ValueError("No image paths provided")
            
        clips = []
        for i, (image_path, duration) in enumerate(zip(image_paths, durations)):
            try:
                # Load and process image
                with Image.open(image_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    # Resize to exact video dimensions
                    target_size = (self.WIDTH, self.HEIGHT)
                    img = img.resize(target_size, Image.Resampling.LANCZOS)
                    # Convert to numpy array
                    img_array = np.array(img)
                
                # Create base clip from numpy array
                base_clip = ImageClip(img_array)
                base_clip = base_clip.set_duration(duration)
                
                # Apply transitions with error handling
                try:
                    clip = self._apply_random_transitions(base_clip, duration)
                except Exception as e:
                    print(f"Transition failed for clip {i + 1}, using basic clip: {str(e)}")
                    clip = base_clip
                
                clips.append(clip)
                print(f"Successfully created clip {i + 1} with transitions")
                
            except Exception as e:
                print(f"Error creating clip {i + 1}: {str(e)}")
                # Create a fallback clip if image processing fails
                fallback_clip = ColorClip(size=(self.WIDTH, self.HEIGHT), 
                                        color=(0, 0, 0)).set_duration(duration)
                clips.append(fallback_clip)
                continue
        
        return clips

    async def get_speech_to_text_segments(self, audio_path: str) -> list[dict]:
        """Get text segments with precise timings using Whisper speech-to-text"""
        try:
            print("Loading Whisper model...")
            model = whisper.load_model("medium")  # Using medium model for better accuracy
            
            # First detect the language
            print("Detecting language...")
            audio = whisper.load_audio(audio_path)
            audio = whisper.pad_or_trim(audio)
            mel = whisper.log_mel_spectrogram(audio).to(model.device)
            _, probs = model.detect_language(mel)
            detected_lang = max(probs, key=probs.get)
            print(f"Detected language: {detected_lang}")
            
            # Set force language based on detection
            force_language = None
            if detected_lang == "vi":
                force_language = "vi"
            elif detected_lang in ["en", "en-US", "en-GB"]:
                force_language = "en"
            
            print(f"Transcribing audio in {force_language if force_language else 'auto'} mode...")
            result = model.transcribe(
                audio_path,
                word_timestamps=True,
                language=force_language,
                task="transcribe",
                condition_on_previous_text=True,
                initial_prompt=f"This is a {force_language} language video." if force_language else None
            )
            
            # Process segments to combine words into phrases
            segments = []
            current_segment = {
                'words': [],
                'start': None,
                'end': None
            }
            word_count = 0
            
            # Process each word with its timing
            for segment in result["segments"]:
                for word_data in segment["words"]:
                    word = word_data["word"].strip()
                    if not word:
                        continue
                        
                    # Start new segment if needed
                    if current_segment['start'] is None:
                        current_segment['start'] = word_data["start"]
                    
                    current_segment['words'].append(word)
                    word_count += 1
                    current_segment['end'] = word_data["end"]
                    
                    # Check if we should create a new segment
                    should_segment = (
                        word_count >= 9 or  # Target 9-10 words per segment
                        word.endswith(('.', '!', '?')) or  # End of sentence
                        (word_count >= 7 and word.endswith((',', ';', ':'))) or  # Natural break point
                        word_count >= 10  # Force break at 10 words
                    )
                    
                    if should_segment and current_segment['words']:
                        # Join words and clean up spacing
                        text = ' '.join(current_segment['words'])
                        # Clean up spacing around punctuation
                        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
                        # Normalize spaces
                        text = ' '.join(text.split())
                        
                        segments.append({
                            'word': text,
                            'start': current_segment['start'],
                            'end': current_segment['end'],
                            'duration': current_segment['end'] - current_segment['start']
                        })
                        
                        # Reset for next segment
                        current_segment = {
                            'words': [],
                            'start': None,
                            'end': None
                        }
                        word_count = 0
            
            # Add any remaining words
            if current_segment['words']:
                # Clean up final segment
                text = ' '.join(current_segment['words'])
                text = re.sub(r'\s+([.,!?;:])', r'\1', text)
                text = ' '.join(text.split())
                
                segments.append({
                    'word': text,
                    'start': current_segment['start'],
                    'end': current_segment['end'],
                    'duration': current_segment['end'] - current_segment['start']
                })
            
            # Post-process segments to ensure consistent language
            if segments:
                # Add small gaps between segments for readability
                for i in range(len(segments) - 1):
                    gap = min(0.1, (segments[i+1]['start'] - segments[i]['end']) / 2)
                    segments[i]['end'] -= gap
                    segments[i+1]['start'] += gap
                    segments[i]['duration'] = segments[i]['end'] - segments[i]['start']
                    segments[i+1]['duration'] = segments[i+1]['end'] - segments[i+1]['start']
            
            return segments
            
        except Exception as e:
            print(f"Error in speech-to-text transcription: {str(e)}")
            traceback.print_exc()
            return []

    async def generate_video(
        self,
        audio_path: str,
        content: Dict[str, Any],
        filename: str,
        background_images: List[str],
        progress_callback=None,
        output_dir: str = None,
        thumbnail_dir: str = None,
        temp_dir: str = None
    ) -> Dict[str, str]:
        try:
            # Use provided directories or defaults
            video_dir = Path(output_dir) if output_dir else self.DEFAULT_VIDEO_DIR
            thumbnail_dir = Path(thumbnail_dir) if thumbnail_dir else self.DEFAULT_THUMBNAIL_DIR
            temp_dir = Path(temp_dir) if temp_dir else self.DEFAULT_TEMP_DIR
            
            # Create directories if they don't exist
            video_dir.mkdir(parents=True, exist_ok=True)
            thumbnail_dir.mkdir(parents=True, exist_ok=True)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Set output paths
            video_path = video_dir / f"{filename}.mp4"
            thumbnail_path = thumbnail_dir / f"{filename}_thumb.jpg"
            temp_audio_path = temp_dir / "temp-audio.m4a"
            
            # Load and preprocess audio
            print("Loading and preprocessing audio...")
            audio = AudioFileClip(audio_path)
            
            # Normalize audio and ensure consistent format
            audio = audio.set_fps(44100)  # Standard audio sampling rate
            audio = audio.set_duration(audio.duration)  # Ensure duration is set correctly
            
            self.DURATION = audio.duration
            print(f"Audio duration: {self.DURATION}")

            # Get speech-to-text segments with precise timings
            print("\nGetting speech-to-text segments...")
            phrase_timings = await self.get_speech_to_text_segments(audio_path)
            if not phrase_timings:
                print("Falling back to script-based timing...")
                phrase_timings = await self.get_precise_word_timings(audio_path, content['script'])
            print(f"Generated {len(phrase_timings)} phrase timings")

            # Calculate durations for background clips
            print("\nCalculating clip durations...")
            if background_images and len(background_images) > 0:
                num_images = len(background_images)
                segment_duration = self.DURATION / num_images
                durations = [segment_duration] * num_images
                print(f"Using {num_images} images with {segment_duration:.2f}s each")

                # Create background clips from image paths
                print("\nCreating background clips...")
                print(f"Using provided background images... (count: {len(background_images)})")
                background_clips = self._create_background_clips(background_images, durations)
                if not background_clips:
                    raise ValueError("Failed to create background clips")
                
                # Concatenate background clips
                background = concatenate_videoclips(background_clips, method="compose")
            else:
                print("No background images provided, using solid color...")
                background = ColorClip(
                    size=(self.WIDTH, self.HEIGHT),
                    color=(0, 0, 0)
                ).set_duration(self.DURATION)

            # Create text clips
            print("\nCreating text clips...")
            text_clips = []
            
            # Create and add title clip first - make it last the entire video
            print("\nCreating title clip...")
            title_clip = self.create_title_clip(content['title'], self.DURATION)  # Show title for entire video
            if title_clip:
                # Position title at the top of the video
                title_clip = title_clip.set_position(('center', self.HEIGHT // 5))  # 1/5 from top
                text_clips.append(title_clip)
                print(f"Added title clip: {content['title']} (duration: {self.DURATION}s)")
            
            # Add subtitle clips
            print("\nCreating subtitle clips...")
            for timing in phrase_timings:
                clip = self.create_text_clip(
                    timing['word'],
                    start_time=timing['start'],
                    duration=timing['duration']
                )
                if clip:
                    text_clips.append(clip)
                    print(f"Added subtitle clip for: {timing['word']}")

            print(f"\nCreated {len(text_clips)} text clips (including title)")
            
            # Create final composition
            print("\nCreating final composition...")
            clips = [background] + text_clips
            print(f"Total clips to compose: {len(clips)}")

            final = CompositeVideoClip(clips, size=(self.WIDTH, self.HEIGHT))
            final = final.set_duration(self.DURATION)
            
            # Write audio to temporary file first
            print("\nPreprocessing audio...")
            audio.write_audiofile(
                str(temp_audio_path),
                fps=44100,
                nbytes=4,
                codec='aac',
                bitrate='192k',
                ffmpeg_params=["-strict", "-2"]
            )
            
            # Load preprocessed audio
            processed_audio = AudioFileClip(str(temp_audio_path))
            final = final.set_audio(processed_audio)

            # Write final video
            print(f"\nWriting video to: {video_path}")
            final.write_videofile(
                str(video_path),
                fps=30,
                codec='libx264',
                audio_codec='aac',
                audio_bitrate='192k',
                bitrate='8000k',
                threads=2,
                logger=MyBarLogger(progress_callback)
            )
            
            # Clean up
            audio.close()
            processed_audio.close()
            final.close()
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            
            # Generate thumbnail from the first frame
            print("\nGenerating thumbnail...")
            video_clip = VideoFileClip(str(video_path))
            thumbnail = video_clip.get_frame(0)  # Get first frame
            thumbnail_img = Image.fromarray(np.uint8(thumbnail))
            thumbnail_img.save(str(thumbnail_path), quality=95)
            video_clip.close()
            print(f"Thumbnail saved to: {thumbnail_path}")
            
            return {
                'video_path': str(video_path),
                'thumbnail_path': str(thumbnail_path)
            }
            
        except Exception as e:
            print(f"Error generating video: {str(e)}")
            traceback.print_exc()
            raise

    def set_format(self, format_type: str):
        """Set the video format and update dimensions"""
        if format_type not in self.VIDEO_FORMATS:
            raise ValueError(f"Invalid format type. Must be one of: {list(self.VIDEO_FORMATS.keys())}")
            
        self.current_format = format_type
        format_spec = self.VIDEO_FORMATS[format_type]
        self.WIDTH = format_spec["width"]
        self.HEIGHT = format_spec["height"]

    def create_title_clip(self, text: str, duration: float) -> TextClip:
        """Create an enhanced title clip with dynamic effects"""
        # Reduce title size
        fontsize = 72 if self.current_format == "shorts" else 60  # Reduced from 90/72
        
        text_clip = TextClip(
            text,
            font='Arial-Bold',
            fontsize=fontsize,
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
        
        # Update floating effect position to 1/6 from top
        float_amount = 8
        final_clip = final_clip.set_position(
            lambda t: ('center', self.HEIGHT * 1/6 + float_amount * math.sin(2 * math.pi * t / 4))
        )
        
        return final_clip

    async def generate_prompts_with_openai(self, script: str) -> List[str]:
        video_format = self.current_format
        """Generate image prompts using OpenAI"""
        try:
            prompt_count = "9-10" if video_format == "shorts" else "18-20"
            
            response = await openai.AsyncOpenAI().chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a professional cinematographer creating video prompts. 
                        Create prompts for black-forest-labs/FLUX.1-schnell-Free model. Your task is to:
                        1. Create 9-10 if shorts format, 18-20 if normal format cinematic, photorealistic prompts
                        2. Each prompt MUST include camera angle and cinematography techniques
                        3. Use these essential cinematography terms in your prompts:
                           - Camera angles: Low angle, High angle, Overhead, FPV (First Person View), Wide angle
                           - Camera aperture: f/1.4, f/2.8, f/4, f/5.6, f/8, f/11, f/16, f/22
                           - Shutter speed: 1/250, 1/500, 1/1000, 1/2000
                           - ISO: 100, 200, 400, 800, 1600, 3200
                           - Focal length: 10mm, 24mm, 35mm, 50mm, 85mm, 135mm, 200mm, 300mm
                           - Shot types: Close up, Medium shot, Wide shot, Macro
                           - Camera movement: Tracking shot, Dolly zoom, Hand held, Steady cam
                           - Lighting: Natural lighting, Diffused lighting, Rim lighting, Lens flare
                           - Time of day: Golden hour, Blue hour, Midday, Dusk, Sunrise, Sunset, Midnight
                           - Weather: Overcast, Clear sky, Dramatic clouds, Rain, Snow, Fog, Wind, Lightning
                        
                        Example good prompts:
                        "Low angle shot of SpaceX rocket launch, golden hour lighting, lens flare, dramatic clouds"
                        "Wide angle tracking shot of Tesla factory, diffused industrial lighting, steady cam movement"
                        "Close up portrait of Elon Musk, shallow depth of field, natural window lighting, office setting"
                        """
                    },
                    {
                        "role": "user",
                        "content": f"""Create {prompt_count} cinematic prompts for this script: 
                        {script}
                        
                        Requirements:
                        - MUST include at least one camera angle/movement term in each prompt
                        - MUST include lighting and atmosphere descriptions
                        - Focus on photorealistic quality
                        - Incorporate relevant subject matter from the script
                        - Each prompt should be under 300 characters
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

    async def analyze_audio_waveform(self, audio_path: str) -> list[dict]:
        """Analyze audio waveform to detect speech segments using multiple features"""
        try:
            # Load the audio file
            y, sr = librosa.load(audio_path)
            
            # Get onset strength with adjusted parameters
            onset_env = librosa.onset.onset_strength(
                y=y, 
                sr=sr,
                hop_length=512,  # Smaller hop length for better precision
                aggregate=np.median  # Use median for more stable detection
            )
            
            # Get speech probability using RMS energy
            S = np.abs(librosa.stft(y))
            rms = librosa.feature.rms(S=S)[0]
            rms_times = librosa.times_like(rms, sr=sr)
            
            # Normalize RMS
            rms = (rms - rms.min()) / (rms.max() - rms.min())
            
            # Get pitch information
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch_times = librosa.times_like(pitches)
            
            # Detect speech onsets with adjusted parameters
            onset_frames = librosa.onset.onset_detect(
                onset_envelope=onset_env,
                sr=sr,
                wait=0.15,      # Minimum time between onset detections
                pre_avg=0.15,   # Time for onset strength to rise
                post_avg=0.15,  # Time for onset strength to fall
                pre_max=0.05,   # Time for local max search
                post_max=0.05,  # Time for local max search
                delta=0.07,     # Minimum onset strength threshold
                backtrack=True  # Find precise onset times
            )
            
            # Convert frames to time
            onset_times = librosa.frames_to_time(onset_frames, sr=sr)
            
            # Get audio duration
            duration = librosa.get_duration(y=y, sr=sr)
            
            # Create segments considering both onsets and RMS energy
            segments = []
            for i in range(len(onset_times)):
                start = onset_times[i]
                # If it's the last onset, use audio duration as end
                end = duration if i == len(onset_times) - 1 else onset_times[i + 1]
                
                # Get RMS energy for this segment
                segment_rms = rms[(rms_times >= start) & (rms_times <= end)]
                avg_energy = np.mean(segment_rms) if len(segment_rms) > 0 else 0
                
                # Only add segments with significant energy and minimum duration
                if avg_energy > 0.2 and (end - start) >= 0.15:
                    # Adjust segment boundaries based on energy
                    start_idx = np.where(rms_times >= start)[0][0]
                    end_idx = np.where(rms_times <= end)[0][-1]
                    
                    # Find the actual speech start/end within the segment
                    while start_idx < len(rms) and rms[start_idx] < 0.2:
                        start_idx += 1
                    while end_idx > 0 and rms[end_idx] < 0.2:
                        end_idx -= 1
                    
                    actual_start = rms_times[start_idx]
                    actual_end = rms_times[end_idx]
                    
                    if actual_end - actual_start >= 0.15:  # Minimum segment duration
                        segments.append({
                            'start': actual_start,
                            'end': actual_end,
                            'duration': actual_end - actual_start,
                            'energy': float(avg_energy)
                        })
            
            return segments
            
        except Exception as e:
            print(f"Error analyzing audio waveform: {str(e)}")
            return []

    async def get_precise_word_timings(self, audio_path: str, subtitle_text: str) -> list[dict]:
        """Get precise word timings with adjustable speed factor"""
        try:
            # Split text into phrases
            phrases = self.split_into_phrases(subtitle_text)
            if not phrases:
                return self._get_fallback_timings(subtitle_text)
            
            # Load audio for duration
            y, sr = librosa.load(audio_path)
            total_duration = librosa.get_duration(y=y, sr=sr)
            
            # Timing parameters - adjusted for better sync
            SPEED_FACTOR = 0.95  # Slightly slower speed for better sync
            BASE_WORD_DURATION = 0.35  # Increased base duration
            MIN_PHRASE_DURATION = 1.8  # Longer minimum duration
            GAP_DURATION = 0.2  # Longer gap between phrases
            
            # Count total words and calculate average time per word
            total_words = sum(len(phrase.split()) for phrase in phrases)
            available_duration = total_duration - (len(phrases) * GAP_DURATION)
            avg_time_per_word = (available_duration * SPEED_FACTOR) / total_words
            
            # Use the larger of calculated or base duration for more natural pacing
            word_duration = max(avg_time_per_word, BASE_WORD_DURATION)
            
            # Generate timings with a slight delay at start
            timings = []
            current_time = 0.1  # Small initial delay
            
            for phrase in phrases:
                # Calculate base duration from words
                words = len(phrase.split())
                base_duration = words * word_duration
                
                # Add extra time for punctuation
                if phrase.strip().endswith(('.', '!', '?')):
                    base_duration += 0.4  # Longer end of sentence pause
                elif phrase.strip().endswith((',', ';', ':')):
                    base_duration += 0.3  # Longer mid-sentence pause
                
                # Ensure minimum duration with some variability
                min_duration = max(MIN_PHRASE_DURATION, words * 0.3)  # Dynamic minimum based on word count
                duration = max(base_duration, min_duration)
                
                # Create timing entry
                timing = {
                    'word': phrase,
                    'start': current_time,
                    'end': current_time + duration,
                    'duration': duration
                }
                timings.append(timing)
                
                # Update current time with gap
                current_time += duration + GAP_DURATION
            
            # If we're over total duration, scale back proportionally
            if current_time > total_duration:
                scale_factor = (total_duration - 0.2) / current_time  # Leave small buffer at end
                for timing in timings:
                    timing['start'] *= scale_factor
                    timing['end'] *= scale_factor
                    timing['duration'] *= scale_factor
            
            return timings
            
        except Exception as e:
            print(f"Error in precise word timing: {str(e)}")
            return self._get_fallback_timings(subtitle_text)

    def _get_fallback_timings(self, subtitle_text: str) -> list[dict]:
        """Generate fallback timings when audio analysis fails"""
        try:
            phrases = self.split_into_phrases(subtitle_text)
            if not phrases:
                return []
            
            # Use same timing logic as main function but with fixed parameters
            SPEED_FACTOR = 0.9
            word_duration = 0.25 * SPEED_FACTOR
            min_duration = 1.2 * SPEED_FACTOR
            gap_duration = 0.08 * SPEED_FACTOR
            
            timings = []
            current_time = 0.0
            
            for phrase in phrases:
                words = len(phrase.split())
                duration = max(words * word_duration, min_duration)
                
                if phrase.strip().endswith(('.', '!', '?')):
                    duration += 0.2 * SPEED_FACTOR
                elif phrase.strip().endswith((',', ';', ':')):
                    duration += 0.1 * SPEED_FACTOR
                
                timing = {
                    'word': phrase,
                    'start': current_time,
                    'end': current_time + duration,
                    'duration': duration
                }
                timings.append(timing)
                
                current_time += duration + gap_duration
            
            return timings
            
        except Exception as e:
            print(f"Error in fallback timing: {str(e)}")
            return []

    def _ensure_numpy_array(self, img):
        """Convert any image type to a numpy array with correct dimensions"""
        try:
            # If it's already a numpy array, just return it
            if isinstance(img, np.ndarray):
                return img
            
            # If it's a PIL Image (including JpegImageFile)
            if hasattr(img, 'convert') and hasattr(img, 'resize'):
                # Ensure RGB mode
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                # Resize to video dimensions using LANCZOS resampling
                img = img.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)
                # Convert to numpy array
                return np.array(img)
            
            raise ValueError(f"Unsupported image type: {type(img)}")
        except Exception as e:
            print(f"Error converting image to numpy array: {e}")
            return None

    def _process_image_response(self, response):
        """Helper method to process image response"""
        import base64
        import io
        import numpy as np
        
        try:
            image_data = base64.b64decode(response.data[0].b64_json)
            image = Image.open(io.BytesIO(image_data))
            
            # Convert image array to PIL Image with proper type handling
            if isinstance(image, np.ndarray):
                # Ensure array is in uint8 format
                if image.dtype != np.uint8:
                    image = (image * 255).astype(np.uint8)
                # Handle both RGB and RGBA images
                if len(image.shape) == 3 and image.shape[2] in [3, 4]:
                    img = Image.fromarray(image)
                else:
                    raise ValueError(f"Invalid image array shape: {image.shape}. Expected (H, W, 3) or (H, W, 4)")
            else:
                img = image
            
            # Resize using LANCZOS resampling
            if img.size != (self.WIDTH, self.HEIGHT):
                img = img.resize((self.WIDTH, self.HEIGHT), Image.Resampling.LANCZOS)
            
            return np.array(img)
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            return np.full((self.HEIGHT, self.WIDTH, 3), [25, 25, 25], dtype=np.uint8)

    def animate_text(self, txt_clip):
        """Add more complex text animations"""
        return txt_clip.fx(
            vfx.slide_in, duration=0.5, side='right'
        ).fx(
            vfx.slide_out, duration=0.5, side='left'
        )

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

    def _align_subtitles_with_timing(self, word_segments: list[dict], subtitle_text: str) -> list[dict]:
        """Align subtitle text with word timings using sequence matching"""
        from difflib import SequenceMatcher
        
        # Clean and split subtitle text
        subtitle_words = self._clean_text(subtitle_text).split()
        detected_words = [self._clean_text(seg["word"]) for seg in word_segments]
        
        aligned_segments = []
        subtitle_idx = 0
        buffer = []
        current_start = None
        
        for i, segment in enumerate(word_segments):
            if subtitle_idx >= len(subtitle_words):
                break
            
            # Compare words using sequence matcher
            similarity = SequenceMatcher(
                None, 
                self._clean_text(segment["word"]), 
                subtitle_words[subtitle_idx]
            ).ratio()
            
            if similarity > 0.8:  # High similarity threshold
                if not current_start:
                    current_start = segment["start"]
                buffer.append(subtitle_words[subtitle_idx])
                
                # Create phrase segment based on word count, punctuation, or length
                should_segment = (
                    len(buffer) >= 9 or  # Target 9-10 words per segment
                    (len(buffer) >= 7 and subtitle_words[subtitle_idx][-1] in '.!?') or  # End sentence if 7+ words
                    subtitle_words[subtitle_idx][-1] in '.!?' or  # Always break at end of sentence
                    (len(buffer) >= 10)  # Force break at 10 words
                )
                
                if should_segment:
                    aligned_segments.append({
                        "word": " ".join(buffer),
                        "start": current_start,
                        "end": segment["end"],
                        "duration": segment["end"] - current_start
                    })
                    buffer = []
                    current_start = None
            
            subtitle_idx += 1
    
        # Add remaining buffer
        if buffer and current_start:
            aligned_segments.append({
                "word": " ".join(buffer),
                "start": current_start,
                "end": word_segments[-1]["end"],
                "duration": word_segments[-1]["end"] - current_start
            })
    
        return aligned_segments

    def _clean_text(self, text: str) -> str:
        """Clean text for comparison"""
        import re
        return re.sub(r'[^\w\s]', '', text.lower().strip())

    def _adjust_timing_gaps(self, segments: list[dict]) -> list[dict]:
        """Adjust timing gaps between segments for smoother transitions"""
        if not segments:
            return []
            
        adjusted_segments = []
        total_duration = segments[-1]['end'] - segments[0]['start']
        
        for i, segment in enumerate(segments):
            if i > 0:
                # Calculate gap with previous segment
                gap = segment['start'] - adjusted_segments[-1]['end']
                
                if gap > 0.3:  # If gap is too large
                    # Extend previous segment and start current one earlier
                    gap_adjustment = gap * 0.4  # Reduce gap by 40%
                    adjusted_segments[-1]['end'] += gap_adjustment / 2
                    segment['start'] -= gap_adjustment / 2
                elif gap < 0:  # If segments overlap
                    # Find middle point and adjust both segments
                    middle = (segment['start'] + adjusted_segments[-1]['end']) / 2
                    adjusted_segments[-1]['end'] = middle
                    segment['start'] = middle
            
            # Ensure minimum duration
            min_duration = 1.5  # Minimum 1.5 seconds for readability
            if segment['end'] - segment['start'] < min_duration:
                segment['end'] = segment['start'] + min_duration
            
            # Update duration
            segment['duration'] = segment['end'] - segment['start']
            adjusted_segments.append(segment)
        
        return adjusted_segments