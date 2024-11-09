from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import asyncio
import os
from typing import Dict, Any
from dotenv import load_dotenv
from src.content_generator import ContentGenerator
from src.audio_generator import AudioGenerator
from src.video_generator import VideoGenerator
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Initialize generators
content_generator = ContentGenerator()
audio_generator = AudioGenerator()
video_generator = VideoGenerator()

@app.route('/api/generate', methods=['POST'])
def generate() -> tuple[Any, int]:
    try:
        data: Dict[str, Any] = request.get_json()
        idea: str = data.get('idea', '')
        
        if not idea:
            return jsonify({'error': 'Video idea is required'}), 400

        # Run the generation process
        result = asyncio.run(generate_content_video(idea))
        
        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<path:filename>')
def download_file(filename: str) -> Any:
    try:
        # Determine file type and set appropriate directory
        if filename.endswith('.mp4'):
            directory = 'contents/video'
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

async def generate_content_video(idea: str) -> Dict[str, Any]:
    """Generate content and video based on idea"""
    try:
        # Generate content
        content = await content_generator.generate_content(idea)
        
        # Generate audio
        filename = f"audio_{int(time.time())}"
        audio_path = await audio_generator.generate_audio(
            script=content['script'],
            filename=filename,
            model="openai"
        )
        
        # Generate video
        video_filename = f"youtube_shorts_{int(time.time())}"
        video_path = await video_generator.generate_video(
            audio_path=audio_path,
            content=content,
            filename=video_filename
        )
        
        # Save content to file
        content_file = save_content_to_file(content, video_path, audio_path)
        
        # Return paths for downloading
        return {
            'video': {
                'filename': os.path.basename(video_path),
                'url': f'/api/download/{os.path.basename(video_path)}'
            },
            'content': {
                'filename': os.path.basename(content_file),
                'url': f'/api/download/{os.path.basename(content_file)}'
            }
        }

    except Exception as e:
        raise Exception(f"Generation failed: {str(e)}")

def save_content_to_file(
    content: Dict[str, Any],
    video_path: str,
    audio_path: str
) -> str:
    """Save generated content to a text file"""
    save_dir = os.path.join("contents", "script")
    os.makedirs(save_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"content_{timestamp}.txt"
    filepath = os.path.join(save_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=== YouTube Shorts Content ===\n\n")
        f.write(f"Title: {content['title']}\n\n")
        f.write(f"Script:\n{content['script']}\n\n")
        f.write(f"Hashtags:\n{' '.join(f'#{tag}' for tag in content['hashtags'])}\n\n")
        f.write(f"Generated Files:\n")
        f.write(f"Audio: {audio_path}\n")
        f.write(f"Video: {video_path}\n")
    
    return filepath

if __name__ == '__main__':
    load_dotenv()
    app.run(debug=True)
