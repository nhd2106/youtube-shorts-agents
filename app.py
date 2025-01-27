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
import time
from datetime import datetime
import threading
import traceback
import sys

app = Flask(__name__)
CORS(app)

# Enable debug mode and hot reload
app.debug = True

# Initialize generators and request tracker
content_generator = ContentGenerator()
audio_generator = AudioGenerator()
video_generator = VideoGenerator()
image_handler = ImageHandler()
request_tracker = RequestTracker()

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
        api_keys: Dict[str, str] = data.get('api_keys', {})
        
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
                voice=voice,
                api_keys=api_keys
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
        api_keys = data.get('api_keys', {})

        if not idea:
            return jsonify({'error': 'No idea provided'}), 400

        # Create new request
        request_id = request_tracker.create_request()

        # Set initial status
        request_tracker.update_request(request_id, status=RequestStatus.PENDING)

        # Generate content with API keys
        content = content_generator.generate(idea, api_keys=api_keys)
        request_tracker.update_request(request_id, status=RequestStatus.GENERATING_CONTENT)

        # Generate audio with API keys
        audio_path = audio_generator.generate(
            content['script'],
            request_id,
            tts_model=tts_model,
            voice=voice,
            api_keys=api_keys
        )
        request_tracker.update_request(request_id, status=RequestStatus.GENERATING_AUDIO)

        # Generate images with API keys
        background_images = image_handler.generate_background_images(
            content['image_prompts'],
            request_id,
            api_keys=api_keys
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

def get_app_data_dir() -> str:
    """Get the application data directory"""
    if getattr(sys, 'frozen', False):
        # When running as PyInstaller bundle on macOS, use ~/Library/Application Support
        home = os.path.expanduser('~')
        app_data = os.path.join(home, 'Library', 'Application Support', 'youtube-shorts-agents')
    else:
        # In development, use current directory
        app_data = os.getcwd()
    
    # Ensure the directory exists
    os.makedirs(app_data, exist_ok=True)
    return app_data

def get_request_directory(request_id: str, content_type: str = None) -> str:
    """
    Get the directory path for a specific request and content type
    
    Args:
        request_id: The unique request ID
        content_type: Optional content type (audio, video, image, script)
    
    Returns:
        Path to the request-specific directory
    """
    try:
        # Get base application data directory
        base_path = get_app_data_dir()
        print(f"App data directory: {base_path}")
        
        # Create contents directory in the app data directory
        contents_dir = os.path.join(base_path, 'contents')
        print(f"Contents directory path: {contents_dir}")
        
        # Create the full path
        base_dir = os.path.join(contents_dir, request_id)
        if content_type:
            base_dir = os.path.join(base_dir, content_type)
        
        print(f"Creating directory at: {base_dir}")
        # Create directory if it doesn't exist
        os.makedirs(base_dir, exist_ok=True)
        
        # Verify directory was created and is writable
        if not os.path.exists(base_dir):
            print(f"Failed to create directory: {base_dir}")
            raise OSError(f"Failed to create directory: {base_dir}")
        
        # Test write permissions
        test_file = os.path.join(base_dir, '.test')
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"Directory is writable: {base_dir}")
        except Exception as e:
            print(f"Directory is not writable: {base_dir}, Error: {str(e)}")
            raise
            
        return base_dir
    except Exception as e:
        print(f"Error in get_request_directory: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        raise

@app.route('/api/download/<request_id>/<content_type>/<path:filename>')
def download_file(request_id: str, content_type: str, filename: str) -> Any:
    try:
        print(f"\nDownload request - ID: {request_id}, Type: {content_type}, File: {filename}")
        
        # Map content types to directories
        content_type_map = {
            'video': 'video',
            'audio': 'audio',
            'script': 'script',
            'thumbnail': 'video',  # Thumbnails are stored in video directory
            'image': 'images'
        }
        
        if content_type not in content_type_map:
            print(f"Invalid content type: {content_type}")
            return jsonify({'error': 'Invalid content type'}), 400
            
        # Get the request-specific directory for the content type
        directory = get_request_directory(request_id, content_type_map[content_type])
        print(f"Got directory path: {directory}")
        
        # Handle thumbnail files
        if content_type == 'thumbnail':
            # Remove any existing extension and add _thumbnail.jpg
            base_name = os.path.splitext(filename)[0]
            filename = f"{base_name}_thumbnail.jpg"
            print(f"Looking for thumbnail: {filename}")
        
        file_path = os.path.join(directory, filename)
        print(f"Constructed file path: {file_path}")
        
        # Verify the file exists and is within the allowed directory
        abs_file_path = os.path.abspath(file_path)
        abs_directory = os.path.abspath(directory)
        
        print(f"Absolute file path: {abs_file_path}")
        print(f"Absolute directory: {abs_directory}")
        
        if not os.path.exists(abs_file_path):
            print(f"File not found: {abs_file_path}")
            # List directory contents to help debug
            if os.path.exists(abs_directory):
                print(f"Directory contents of {abs_directory}:")
                for f in os.listdir(abs_directory):
                    print(f"  - {f}")
            return jsonify({'error': 'File not found'}), 404
            
        if not abs_file_path.startswith(abs_directory):
            print(f"Invalid file path: {abs_file_path}")
            return jsonify({'error': 'Invalid file path'}), 403

        # Check file permissions
        if not os.access(abs_file_path, os.R_OK):
            print(f"File not readable: {abs_file_path}")
            return jsonify({'error': 'File not readable'}), 403

        print(f"Serving file: {abs_file_path}")
        
        # Set appropriate MIME type based on content type
        mime_types = {
            'video': 'video/mp4',
            'audio': 'audio/mpeg',
            'script': 'text/plain',
            'thumbnail': 'image/jpeg',
            'image': 'image/jpeg'
        }
        
        try:
            return send_file(
                abs_file_path,
                as_attachment=True,
                download_name=filename,
                mimetype=mime_types.get(content_type, 'application/octet-stream')
            )
        except Exception as e:
            print(f"Error in send_file: {str(e)}")
            raise

    except Exception as e:
        print(f"Error serving file: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

async def generate_content_video(
    request_id: str,
    idea: str,
    video_format: str = 'shorts',
    tts_model: str = 'edge',
    voice: str = None,
    api_keys: Dict[str, str] = None
) -> None:
    """Generate content and video based on idea and parameters"""
    try:
        print(f"Starting content generation with format: {video_format}")
        
        # Set video format for all generators at the start
        video_generator.set_format(video_format)
        image_handler.set_format(video_format)
        
        # Create all required directories at once
        dirs = [
            get_request_directory(request_id, 'audio'),
            get_request_directory(request_id, 'images'),
            get_request_directory(request_id, 'video'),
            get_request_directory(request_id, 'script')
        ]
        
        # Update status to generating content
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.GENERATING_CONTENT,
            progress=10
        )
        
        # Generate content with format and API keys
        content = await content_generator.generate_content(idea, video_format, api_keys)
        
        # Start all generation tasks in parallel
        audio_filename = f"{request_id}_audio"
        video_filename = f"{request_id}_{video_format}_video"
        
        # Create all tasks at once
        tasks = [
            # Audio generation task with API keys
            audio_generator.generate_audio(
                script=content['script'],
                filename=audio_filename,
                model=tts_model,
                voice=voice,
                output_dir=dirs[0],  # audio dir
                api_keys=api_keys
            ),
            # Image prompts generation task with API keys
            video_generator.generate_prompts_with_openai(content['script'], api_keys),
        ]
        
        # Update status for parallel processing
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.GENERATING_AUDIO,
            progress=30
        )
        
        # Wait for both audio and prompts
        audio_path, prompts = await asyncio.gather(*tasks)
        
        # Start image generation immediately after getting prompts
        request_tracker.update_request(
            request_id=request_id,
            status=RequestStatus.GENERATING_IMAGES,
            progress=40
        )
        
        # Calculate required number of images based on video format
        required_images = 10 if video_format == "shorts" else 20
        
        # Process extracted images from URL if available
        image_paths = []
        if content.get('image_urls'):
            print(f"Processing {len(content['image_urls'])} extracted images from URL")
            # Download and process extracted images
            for url in content['image_urls']:
                try:
                    image_path = await image_handler.download_and_process_image(
                        url,
                        output_dir=dirs[1]  # images dir
                    )
                    if image_path:
                        image_paths.append(image_path)
                except Exception as e:
                    print(f"Error processing image from URL {url}: {str(e)}")
                    continue
            
            print(f"Successfully processed {len(image_paths)} images from URLs")
        
        # Generate additional images if we don't have enough
        if len(image_paths) < required_images:
            remaining_images = required_images - len(image_paths)
            print(f"Need {remaining_images} more images. Generating with AI...")
            
            # Use prompts for the remaining images needed
            selected_prompts = prompts[:remaining_images]
            if not selected_prompts:
                print("No prompts available, generating new ones...")
                # If we don't have enough prompts, generate more
                selected_prompts = await video_generator.generate_prompts_with_openai(
                    content['script'], 
                    api_keys,
                    count=remaining_images
                )
            
            additional_images = await image_handler.generate_background_images(
                selected_prompts,
                request_id,
                output_dir=dirs[1],  # images dir
                api_keys=api_keys
            )
            print(f"Generated {len(additional_images)} additional images")
            image_paths.extend(additional_images)
        elif len(image_paths) > required_images:
            print(f"Using only the first {required_images} images")
            image_paths = image_paths[:required_images]
        
        print(f"Final image count: {len(image_paths)}")
        
        # Verify we have enough images
        if len(image_paths) < required_images:
            raise Exception(f"Failed to generate enough images. Required: {required_images}, Got: {len(image_paths)}")
        
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
            output_dir=dirs[2],  # video dir
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
            output_dir=dirs[3]  # script dir
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
        # Use app data directory if no output dir specified
        app_data = get_app_data_dir()
        save_dir = os.path.join(app_data, 'contents', 'script')
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

def delete_request_directory(request_id: str) -> None:
    """Delete all content associated with a request ID"""
    try:
        base_path = get_app_data_dir()
        contents_dir = os.path.join(base_path, 'contents')
        
        # List of directories to check and delete
        directories = [
            os.path.join(contents_dir, request_id),  # Main request directory
            os.path.join(contents_dir, 'video', request_id),  # Video directory (includes thumbnails)
            os.path.join(contents_dir, 'audio', request_id),  # Audio directory
            os.path.join(contents_dir, 'images', request_id),  # Images directory
            os.path.join(contents_dir, 'script', request_id)   # Script directory
        ]
        
        deleted = False
        for directory in directories:
            if os.path.exists(directory):
                print(f"Deleting directory: {directory}")
                import shutil
                shutil.rmtree(directory)
                print(f"Successfully deleted directory: {directory}")
                deleted = True
                
        if not deleted:
            print(f"No directories found for request ID: {request_id}")
            raise FileNotFoundError(f"No content found for request ID: {request_id}")
            
    except Exception as e:
        print(f"Error deleting directory: {str(e)}")
        raise

@app.route('/api/content/<request_id>', methods=['DELETE'])
def delete_content(request_id: str) -> tuple[Any, int]:
    """Delete all content associated with a request ID"""
    try:
        print(f"\nDelete request - ID: {request_id}")
        success = False
        
        # Try to delete from request tracker if it exists
        request_data = request_tracker.get_request(request_id)
        if request_data:
            request_tracker.delete_request(request_id)
            success = True
        
        # Try to delete files regardless of request tracker status
        try:
            delete_request_directory(request_id)
            success = True
        except FileNotFoundError as e:
            print(f"Directory not found: {str(e)}")
            # Only return 404 if both tracker and files don't exist
            if not success:
                return jsonify({'error': 'Content not found'}), 404
        except PermissionError as e:
            print(f"Permission error: {str(e)}")
            return jsonify({'error': 'Permission denied when deleting files'}), 403
        except Exception as e:
            print(f"Error deleting files: {str(e)}")
            # If we deleted from tracker but failed to delete files, still return success
            if not success:
                return jsonify({'error': f'Error deleting files: {str(e)}'}), 500
        
        return jsonify({
            'message': 'Content deleted successfully',
            'request_id': request_id
        }), 200
        
    except Exception as e:
        print(f"Error in delete_content: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5123))
    print(f"\nStarting server...")
    print(f"Running mode: {'PyInstaller bundle' if getattr(sys, 'frozen', False) else 'Development'}")
    print(f"Working directory: {os.getcwd()}")
    if getattr(sys, 'frozen', False):
        print(f"Executable path: {sys.executable}")
        print(f"App data directory: {get_app_data_dir()}")
    print(f"Port: {port}\n")
    
    # Ensure app data directory exists
    app_data = get_app_data_dir()
    print(f"Using app data directory: {app_data}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=True,
        use_reloader=True
    )
