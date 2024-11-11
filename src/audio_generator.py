import os
import edge_tts
import asyncio
from gtts import gTTS
from openai import OpenAI
# import torch
# from TTS.api import TTS

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
        }
    }

    def get_available_models(self) -> dict:
        """Return available TTS models and their voices"""
        return self.AVAILABLE_MODELS

    async def generate_audio(self, script: str, filename: str, model: str = "edge", voice: str = None) -> str:
        """Generate audio file from script"""
        try:
            # Validate model and voice selection
            if model not in self.AVAILABLE_MODELS:
                raise ValueError(f"Invalid model selected. Available models: {list(self.AVAILABLE_MODELS.keys())}")
            
            selected_model = self.AVAILABLE_MODELS[model]
            voice = voice or selected_model["default_voice"]
            
            if voice not in selected_model["voices"]:
                raise ValueError(f"Invalid voice for {model}. Available voices: {selected_model['voices']}")

            output_dir = "contents/audio"
            os.makedirs(output_dir, exist_ok=True)
            
            output_path = os.path.join(output_dir, f"{filename}.mp3")
            
            if model == "edge":
                # Edge TTS rate adjustment using communicate options
                communicate = edge_tts.Communicate(script, voice or "vi-VN-NamMinhNeural")
                communicate.tts_config.rate = 1.25  # Increase speed by 25%
                await communicate.save(output_path)
            elif model == "gtts":
                # Unfortunately, gTTS doesn't support speed adjustment directly
                tts = gTTS(text=script, lang='vi')
                tts.save(output_path)
            elif model == "openai":
                client = OpenAI()
                response = client.audio.speech.create(
                    model="tts-1",
                    voice=voice,
                    input=script,
                    speed=1.25  # OpenAI TTS supports speed adjustment
                )
                response.stream_to_file(output_path)
            # elif model == "TTS":
            #     # Initialize TTS with a Vietnamese-compatible model
            #     tts = TTS(model_name="tts_models/vi/vivos/vits", progress_bar=False)
            #     # Generate audio with specific settings for better Vietnamese quality
            #     tts.tts_to_file(
            #         text=script,
            #         file_path=output_path,
            #         speaker_wav=None,  # Optional: can be used for voice cloning
            #         language="vi"
            #     )
            
            return output_path
            
        except Exception as e:
            print(f"Error generating audio: {str(e)}")
            raise