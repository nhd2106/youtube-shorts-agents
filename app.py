from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import asyncio
import os
from typing import Dict, Any
from src.content_generator import ContentGenerator
from src.audio_generator import AudioGenerator
from src.video_generator import VideoGenerator
from src.image_handler import ImageHandler
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Initialize generators
content_generator = ContentGenerator()
audio_generator = AudioGenerator()
video_generator = VideoGenerator()
image_handler = ImageHandler()

@app.route('/api/models', methods=['GET'])
def get_available_models() -> tuple[Any, int]:
    """Get available TTS models and voices"""
    try:
        models = audio_generator.get_available_models()
        return jsonify(models), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate() -> tuple[Any, int]:
    try:
        data: Dict[str, Any] = request.get_json()
        idea: str = data.get('idea', '')
        video_format: str = data.get('format', 'shorts')  # 'shorts' or 'normal'
        tts_model: str = data.get('tts_model', 'edge')    # TTS model selection
        voice: str = data.get('voice', None)              # Voice selection
        
        if not idea:
            return jsonify({'error': 'Video idea is required'}), 400

        # Validate video format
        if video_format not in ['shorts', 'normal']:
            return jsonify({'error': 'Invalid video format'}), 400

        # Validate TTS model and voice
        available_models = audio_generator.get_available_models()
        if tts_model not in available_models:
            return jsonify({'error': 'Invalid TTS model'}), 400

        if voice and voice not in available_models[tts_model]['voices']:
            return jsonify({'error': 'Invalid voice for selected model'}), 400

        # Run the generation process with parameters
        result = asyncio.run(generate_content_video(
            idea=idea,
            video_format=video_format,
            tts_model=tts_model,
            voice=voice
        ))
        
        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<path:filename>')
def download_file(filename: str) -> Any:
    try:
        # Determine file type and set appropriate directory
        if filename.endswith('.mp4'):
            directory = 'contents/video'
        elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
            directory = 'contents/thumbnail'
        elif filename.endswith('.txt'):
            directory = 'contents/script'
        else:
            return jsonify({'error': 'Invalid file type'}), 400

        file_path = os.path.join(directory, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

async def generate_content_video(
    idea: str,
    video_format: str = 'shorts',
    tts_model: str = 'edge',
    voice: str = None
) -> Dict[str, Any]:
    """Generate content and video based on idea and parameters"""
    try:
        # Generate content with format
        content = await content_generator.generate_content(idea, video_format)
        
        # Start audio generation and image generation in parallel
        filename = f"audio_{int(time.time())}"
        video_filename = f"video_{video_format}_{int(time.time())}"
        
        # Create tasks for parallel execution
        audio_task = audio_generator.generate_audio(
            script=content['script'],
            filename=filename,
            model=tts_model,
            voice=voice
        )
        
        # Start generating images while audio is being generated
        prompts = await video_generator.generate_prompts_with_openai(content['script'])
        image_task = image_handler.generate_images(prompts)
        
        # Wait for both tasks to complete
        audio_path, image_paths = await asyncio.gather(audio_task, image_task)
        
        # Verify audio file exists before proceeding
        if not os.path.exists(audio_path):
            raise Exception("Audio generation failed or file not found")
        
        # Generate video with the prepared audio and images
        video_result = await video_generator.generate_video(
            audio_path=audio_path,
            content=content,
            filename=video_filename,
            background_images=image_paths,
            progress_callback=None
        )
        
        if not video_result:
            raise Exception("Video generation failed")

        video_path = video_result['video_path']
        thumbnail_path = video_result['thumbnail_path']
        
        # Save content to file with additional metadata
        content_file = save_content_to_file(
            content=content,
            video_path=video_path,
            audio_path=audio_path,
            tts_model=tts_model,
            voice=voice
        )
        
        # Return paths for downloading
        return {
            'video': {
                'filename': os.path.basename(video_path),
                'url': f'/api/download/{os.path.basename(video_path)}'
            },
            'thumbnail': {
                'filename': os.path.basename(thumbnail_path) if thumbnail_path else None,
                'url': f'/api/download/{os.path.basename(thumbnail_path)}' if thumbnail_path else None
            },
            'content': {
                'filename': os.path.basename(content_file),
                'url': f'/api/download/{os.path.basename(content_file)}'
            },
            'metadata': {
                'format': video_format,
                'tts_model': tts_model,
                'voice': voice
            }
        }

    except Exception as e:
        raise Exception(f"Generation failed: {str(e)}")

def save_content_to_file(
    content: Dict[str, Any],
    video_path: str,
    audio_path: str,
    tts_model: str,
    voice: str = None
) -> str:
    """Save generated content to a text file with additional metadata"""
    save_dir = os.path.join("contents", "script")
    os.makedirs(save_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"content_{timestamp}.txt"
    filepath = os.path.join(save_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=== YouTube Content ===\n\n")
        f.write(f"Title: {content['title']}\n\n")
        f.write(f"Script:\n{content['script']}\n\n")
        f.write(f"Hashtags:\n{' '.join(f'#{tag}' for tag in content['hashtags'])}\n\n")
        f.write(f"Format: {content.get('format', {}).get('type', 'shorts')}\n")
        f.write(f"TTS Model: {tts_model}\n")
        f.write(f"Voice: {voice or 'default'}\n\n")
        f.write(f"Generated Files:\n")
        f.write(f"Audio: {audio_path}\n")
        f.write(f"Video: {video_path}\n")
    
    return filepath

if __name__ == '__main__':
    app.run(debug=True)
