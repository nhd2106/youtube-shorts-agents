from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
import asyncio
import os
from typing import Dict, Any
from src.content_generator import ContentGenerator
from src.audio_generator import AudioGenerator
from src.video_generator import VideoGenerator
from src.image_handler import ImageHandler
from src.request_tracker import RequestTracker, RequestStatus
from src.youtube_uploader import YouTubeUploader
import time
from datetime import datetime
import threading
import traceback

app = Flask(__name__)
CORS(app)

# Initialize generators and request tracker
content_generator = ContentGenerator()
audio_generator = AudioGenerator()
video_generator = VideoGenerator()
image_handler = ImageHandler()
request_tracker = RequestTracker()
youtube_uploader = YouTubeUploader()

# Start background task to clean old requests
def clean_old_requests():
    while True:
        request_tracker.clean_old_requests()
        time.sleep(3600)  # Clean every hour

cleaning_thread = threading.Thread(target=clean_old_requests, daemon=True)
cleaning_thread.start()

@app.route('/')
def home():
    """Render the homepage"""
    return render_template('index.html')

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
        video_format: str = data.get('format', 'shorts')
        tts_model: str = data.get('tts_model', 'edge')
        voice: str = data.get('voice', None)
        
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

        # Set the format for image and video generation
        image_handler.set_format(video_format)
        video_generator.set_format(video_format)

        # Create request and start generation in background
        request_id = request_tracker.create_request()
        
        # Start async generation in a separate thread
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(generate_content_video(
                request_id=request_id,
                idea=idea,
                video_format=video_format,
                tts_model=tts_model,
                voice=voice
            ))
            loop.close()
            
        thread = threading.Thread(target=run_async)
        thread.start()
        
        # Return request ID immediately
        return jsonify({
            'request_id': request_id,
            'status': 'pending',
            'message': 'Generation started'
        }), 202

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/status/<request_id>', methods=['GET'])
def get_status(request_id: str) -> tuple[Any, int]:
    """Get status of a generation request"""
    try:
        request_data = request_tracker.get_request(request_id)
        if not request_data:
            return jsonify({'error': 'Request not found'}), 404

        # Add stage descriptions for better UX
        stage_descriptions = {
            'pending': 'Initializing...',
            'generating_content': 'Generating video script and content...',
            'generating_audio': 'Converting script to audio...',
            'generating_images': 'Creating background images...',
            'generating_video': 'Assembling final video...',
            'completed': 'Video generation completed!',
            'failed': 'Video generation failed.'
        }

        response = {
            **request_data,
            'stage_description': stage_descriptions.get(request_data['status'], ''),
            'estimated_time_remaining': None  # Could be implemented based on average completion times
        }
        
        return jsonify(response), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prepare-video-data', methods=['POST'])
def prepare_video_data() -> tuple[Any, int]:
    """Generate and return all necessary data for client-side video rendering"""
    try:
        data: Dict[str, Any] = request.get_json()
        request_id = data.get('request_id', str(int(time.time())))
        idea = data.get('idea')
        video_format = data.get('video_format', 'shorts')
        tts_model = data.get('tts_model', 'edge')
        voice = data.get('voice')

        if not idea:
            return jsonify({'error': 'No idea provided'}), 400

        # Create new request
        request_id = request_tracker.create_request()

        # Set initial status
        request_tracker.update_request(request_id, status=RequestStatus.PENDING)

        # Generate content
        content = content_generator.generate(idea)
        request_tracker.update_request(request_id, status=RequestStatus.GENERATING_CONTENT)

        # Generate audio
        audio_path = audio_generator.generate(
            content['script'],
            request_id,
            tts_model=tts_model,
            voice=voice
        )
        request_tracker.update_request(request_id, status=RequestStatus.GENERATING_AUDIO)

        # Generate images
        background_images = image_handler.generate_background_images(
            content['image_prompts'],
            request_id
        )
        request_tracker.update_request(request_id, status=RequestStatus.GENERATING_IMAGES)

        # Set video format and get dimensions
        video_generator.set_format(video_format)
        
        # Get word timings for captions
        word_timings = video_generator.get_precise_word_timings(audio_path, content['script'])

        # Prepare response data
        response_data = {
            'request_id': request_id,
            'content': content,
            'paths': {
                'audio': audio_path,
                'background_images': background_images
            },
            'video_settings': {
                'format': video_format,
                'width': video_generator.WIDTH,
                'height': video_generator.HEIGHT,
                'duration': video_generator.DURATION
            },
            'timings': word_timings,
            'title': {
                'text': content['title'],
                'position': {
                    'x': 'center',
                    'y': video_generator.HEIGHT // 5  # 1/5 from top
                }
            }
        }

        request_tracker.update_request(request_id, status=RequestStatus.COMPLETED, result=response_data)
        return jsonify(response_data), 200

    except Exception as e:
        print(f"Error in prepare_video_data: {str(e)}")
        traceback.print_exc()
        if 'request_id' in locals():
            request_tracker.update_request(request_id, status=RequestStatus.FAILED, error=str(e))
        return jsonify({'error': str(e)}), 500

def get_request_directory(request_id: str, content_type: str = None) -> str:
    """
    Get the directory path for a specific request and content type
    
    Args:
        request_id: The unique request ID
        content_type: Optional content type (audio, video, image, script)
    
    Returns:
        Path to the request-specific directory
    """
    base_dir = os.path.join('contents', request_id)
    if content_type:
        base_dir = os.path.join(base_dir, content_type)
    
    # Create directory if it doesn't exist
    os.makedirs(base_dir, exist_ok=True)
    return base_dir

@app.route('/api/download/<request_id>/<content_type>/<path:filename>')
def download_file(request_id: str, content_type: str, filename: str) -> Any:
    try:
        # Get the request-specific directory for the content type
        directory = get_request_directory(request_id, content_type)
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

@app.route('/api/upload/youtube/<request_id>', methods=['POST'])
async def upload_to_youtube(request_id: str) -> tuple[Any, int]:
    """Upload a generated video to YouTube"""
    try:
        # Get request data
        request_data = request_tracker.get_request(request_id)
        if not request_data:
            return jsonify({'error': 'Request not found'}), 404

        if request_data['status'] != 'completed':
            return jsonify({'error': 'Video generation not completed'}), 400

        # Get video details from request
        data = request.get_json()
        title = data.get('title')
        description = data.get('description')
        tags = data.get('tags', [])
        privacy_status = data.get('privacy_status', 'private')

        if not title or not description:
            return jsonify({'error': 'Title and description are required'}), 400

        # Get video path from request result
        video_filename = request_data['result']['video']['filename']
        video_path = os.path.join(get_request_directory(request_id, 'video'), video_filename)

        if not os.path.exists(video_path):
            return jsonify({'error': 'Video file not found'}), 404

        # Upload to YouTube
        upload_result = await youtube_uploader.upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            is_shorts=request_data['result']['metadata']['format'] == 'shorts',
            privacy_status=privacy_status
        )

        return jsonify(upload_result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

async def generate_content_video(
    request_id: str,
    idea: str,
    video_format: str = 'shorts',
    tts_model: str = 'edge',
    voice: str = None
) -> None:
    """Generate content and video based on idea and parameters"""
    try:
        print(f"Starting content generation with format: {video_format}")
        
        # Set video format for all generators at the start
        video_generator.set_format(video_format)
        image_handler.set_format(video_format)
        
        # Update status to generating content
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.GENERATING_CONTENT,
            progress=10
        )
        
        # Generate content with format
        content = await content_generator.generate_content(idea, video_format)
        
        print(f"Content generated, current format: {video_generator.current_format}")
        
        # Start audio generation and image generation in parallel
        audio_filename = f"{request_id}_audio"
        video_filename = f"{request_id}_{video_format}_video"
        
        # Update status to generating audio and images
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.GENERATING_AUDIO,
            progress=30
        )
        
        # Create tasks for parallel execution
        audio_task = audio_generator.generate_audio(
            script=content['script'],
            filename=audio_filename,
            model=tts_model,
            voice=voice,
            output_dir=get_request_directory(request_id, 'audio')
        )
        
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.GENERATING_IMAGES,
            progress=40
        )
        
        # Verify format is still correct before image generation
        print(f"Before image generation, format: {image_handler.current_format}")
        
        # Start generating images while audio is being generated
        prompts = await video_generator.generate_prompts_with_openai(content['script'])
        image_task = image_handler.generate_images(
            prompts,
            output_dir=get_request_directory(request_id, 'images')
        )
        
        # Wait for both tasks to complete
        audio_path, image_paths = await asyncio.gather(audio_task, image_task)
        
        # Verify format is still correct before video generation
        print(f"Before video generation, format: {video_generator.current_format}")
        
        # Verify audio file exists before proceeding
        if not os.path.exists(audio_path):
            raise Exception("Audio generation failed or file not found")
        
        # Update status to generating video
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.GENERATING_VIDEO,
            progress=70
        )
        
        # Generate video with the prepared audio and images
        video_result = await video_generator.generate_video(
            audio_path=audio_path,
            content=content,
            filename=video_filename,
            output_dir=get_request_directory(request_id, 'video'),
            background_images=image_paths,
            progress_callback=lambda p: request_tracker.update_request(
                request_id=request_id,
                progress=70 + int(p * 0.3)  # Scale progress from 70 to 100
            )
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
            voice=voice,
            output_dir=get_request_directory(request_id, 'script')
        )
        
        # Update request with final result
        result = {
            'video': {
                'filename': os.path.basename(video_path),
                'url': f'/api/download/{request_id}/video/{os.path.basename(video_path)}'
            },
            'thumbnail': {
                'filename': os.path.basename(thumbnail_path) if thumbnail_path else None,
                'url': f'/api/download/{request_id}/thumbnail/{os.path.basename(thumbnail_path)}' if thumbnail_path else None
            },
            'content': {
                'filename': os.path.basename(content_file),
                'url': f'/api/download/{request_id}/script/{os.path.basename(content_file)}'
            },
            'metadata': {
                'format': video_format,
                'tts_model': tts_model,
                'voice': voice
            }
        }
        
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.COMPLETED,
            progress=100,
            result=result
        )

    except Exception as e:
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.FAILED,
            error=str(e)
        )

def save_content_to_file(
    content: Dict[str, Any],
    video_path: str,
    audio_path: str,
    tts_model: str,
    voice: str = None,
    output_dir: str = None
) -> str:
    """Save generated content to a text file with additional metadata"""
    if not output_dir:
        save_dir = os.path.join("contents", "script")
    else:
        save_dir = output_dir
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
    port = int(os.getenv('PORT', 5123))
    host = os.getenv('HOST', '0.0.0.0')
    app.run(host=host, port=port, debug=True)
