import os
import edge_tts
import asyncio
from gtts import gTTS
from openai import OpenAI
# import torch
# from TTS.api import TTS

class AudioGenerator:
    async def list_voices(self, model: str) -> list:
        """List available voices for the selected model"""
        try:
            if model == "edge":
                voices = await edge_tts.list_voices()
                return voices
            return []
        
        except Exception as e:
            print(f"Error listing voices: {str(e)}")
            return []

    async def generate_audio(self, script: str, filename: str, model: str = "edge", voice: str = None) -> str:
        """Generate audio file from script"""
        try:
            output_dir = "contents/audio"
            os.makedirs(output_dir, exist_ok=True)
            
            output_path = os.path.join(output_dir, f"{filename}.mp3")
            
            if model == "edge":
                communicate = edge_tts.Communicate(script, voice or "vi-VN-NamMinhNeural")
                await communicate.save(output_path)
            elif model == "gtts":
                tts = gTTS(text=script, lang='vi')
                tts.save(output_path)
            elif model == "openai":
                client = OpenAI()
                response = client.audio.speech.create(
                    model="tts-1",
                    voice="echo",
                    input=script
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