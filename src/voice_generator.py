import os
from openai import OpenAI
from pathlib import Path

class VoiceGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def generate_voice(self, script: str, output_path: str) -> str:
        response = await self.client.audio.speech.create(
            model="tts-1",
            voice="alloy",  # You can change the voice
            input=script
        )
        
        # Save the audio file
        audio_path = Path(output_path) / "output.mp3"
        response.stream_to_file(str(audio_path))
        
        return str(audio_path) 