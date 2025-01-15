import edge_tts
import asyncio
from gtts import gTTS
from openai import OpenAI
from pathlib import Path
import hashlib
import json
from elevenlabs import ElevenLabs

class AudioGenerator:
    AVAILABLE_MODELS = {
        "edge": {
            "name": "Edge TTS",
            "default_voice": "vi-VN-NamMinhNeural",
            "voices": ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"]
        },
        "gtts": {
            "name": "Google TTS",
            "default_voice": "vi",
            "voices": ["vi"]
        },
        "openai": {
            "name": "OpenAI TTS",
            "default_voice": "echo",
            "voices": ["echo", "alloy", "fable", "onyx", "nova", "shimmer"]
        },
        "elevenlabs": {
            "name": "ElevenLabs",
            "default_voice": "t1LUnfTt7pXaYjubT04d",
            "voices": ["t1LUnfTt7pXaYjubT04d","WVkYyTxxVgMOsw1IIVL0", "7hsfEc7irDn6E8br0qfw"]
        }
    }

    def __init__(self):
        self.cache_dir = Path("contents/cache/audio")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.openai_client = None
        self.elevenlabs_client = None
        self.semaphore = asyncio.Semaphore(3)  # Limit concurrent API calls

    def _init_openai_client(self, api_key: str):
        """Initialize OpenAI client with API key"""
        if not api_key:
            raise ValueError("OpenAI API key is required for OpenAI TTS")
        self.openai_client = OpenAI(api_key=api_key)

    def _init_elevenlabs_client(self, api_key: str):
        """Initialize ElevenLabs client with API key"""
        if not api_key:
            raise ValueError("ElevenLabs API key is required for ElevenLabs TTS")
        self.elevenlabs_client = ElevenLabs(api_key=api_key)

    def get_available_models(self) -> dict:
        """Return available TTS models and their voices"""
        return self.AVAILABLE_MODELS

    def _get_cache_key(self, script: str, model: str, voice: str) -> str:
        """Generate a unique cache key for the audio request"""
        data = {
            'script': script,
            'model': model,
            'voice': voice
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def _get_cached_audio(self, cache_key: str) -> str:
        """Check if audio exists in cache"""
        cache_path = self.cache_dir / f"{cache_key}.mp3"
        return str(cache_path) if cache_path.exists() else None

    async def generate_audio(
        self,
        script: str,
        filename: str,
        model: str = "edge",
        voice: str = None,
        output_dir: str = None,
        api_keys: dict = None
    ) -> str:
        """Generate audio file from script with caching"""
        try:
            # Validate model and voice selection
            if model not in self.AVAILABLE_MODELS:
                raise ValueError(f"Invalid model selected. Available models: {list(self.AVAILABLE_MODELS.keys())}")
            
            selected_model = self.AVAILABLE_MODELS[model]
            voice = voice or selected_model["default_voice"]
            
            if voice not in selected_model["voices"]:
                raise ValueError(f"Invalid voice for {model}. Available voices: {selected_model['voices']}")

            # Check cache first
            cache_key = self._get_cache_key(script, model, voice)
            cached_path = self._get_cached_audio(cache_key)
            
            if cached_path:
                # Use provided output directory or default
                if not output_dir:
                    output_dir = "contents/audio"
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_path = output_dir / f"{filename}.mp3"
                
                # Copy from cache to output directory
                import shutil
                shutil.copy2(cached_path, output_path)
                return str(output_path)

            async with self.semaphore:
                # Use provided output directory or default
                if not output_dir:
                    output_dir = "contents/audio"
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_path = output_dir / f"{filename}.mp3"
                cache_path = self.cache_dir / f"{cache_key}.mp3"
                
                if model == "edge":
                    # Edge TTS rate adjustment using communicate options
                    communicate = edge_tts.Communicate(script, voice or "vi-VN-NamMinhNeural")
                    communicate.tts_config.rate = 1.25  # Increase speed by 25%
                    await communicate.save(str(output_path))
                elif model == "gtts":
                    # Unfortunately, gTTS doesn't support speed adjustment directly
                    tts = gTTS(text=script, lang='vi')
                    tts.save(str(output_path))
                elif model == "openai":
                    if not api_keys or not api_keys.get('openai'):
                        raise ValueError("OpenAI API key is required for OpenAI TTS")
                    self._init_openai_client(api_keys['openai'])
                    response = self.openai_client.audio.speech.create(
                        model="tts-1",
                        voice=voice,
                        input=script,
                        speed=1.25  # OpenAI TTS supports speed adjustment
                    )
                    response.stream_to_file(str(output_path))
                elif model == "elevenlabs":
                    if not api_keys or not api_keys.get('elevenlabs'):
                        raise ValueError("ElevenLabs API key is required for ElevenLabs TTS")
                    self._init_elevenlabs_client(api_keys['elevenlabs'])
                    audio_stream = self.elevenlabs_client.text_to_speech.convert(
                        text=script,
                        voice_id=voice,
                        model_id="eleven_turbo_v2_5",
                        output_format="mp3_22050_32"
                    )
                    
                    # Save the streaming response to the output file
                    with open(output_path, 'wb') as audio_file:
                        for chunk in audio_stream:
                            audio_file.write(chunk)
                
                # Check if file was generated
                if not output_path.exists():
                    raise RuntimeError("Audio generation failed")
                
                # Cache the generated audio
                import shutil
                shutil.copy2(output_path, cache_path)
                
                return str(output_path)
            
        except Exception as e:
            print(f"Error generating audio: {str(e)}")
            raise