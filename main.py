import asyncio
import os
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from src.content_generator import ContentGenerator
from src.audio_generator import AudioGenerator
from src.video_generator import VideoGenerator
import time
import json
from datetime import datetime
import shutil
import sys

console = Console()

async def generate_content(generator: ContentGenerator, idea: str) -> dict:
    """Generate content based on user input"""
    try:
        content = await generator.generate_content(idea)
        return content
    except Exception as e:
        console.print(f"[red]Error generating content: {str(e)}[/red]")
        raise

async def generate_audio(audio_generator: AudioGenerator, script: str) -> str:
    """Generate audio from script"""
    try:
        console.print("[yellow]Starting audio generation process...[/yellow]")
        filename = f"audio_{int(time.time())}"
        
        # Debug log with more details
        console.print(f"[dim]Debug: Script length: {len(script)} characters[/dim]")
        console.print(f"[dim]Debug: First 100 chars of script: {script[:100]}...[/dim]")
        
        # Simplified model selection - remove user prompt for testing
        model = "openai"  # Force edge TTS for testing
        console.print(f"[dim]Debug: Using model: {model}[/dim]")
        
        # Use a specific voice without fetching list
        voice = None  # Changed to a common English voice
        console.print(f"[dim]Debug: Using voice: {voice}[/dim]")
        
        console.print("[yellow]Starting audio generation...[/yellow]")
        
        # Increase timeout and add more error handling
        try:
            audio_path = await asyncio.wait_for(
                audio_generator.generate_audio(
                    script=script,
                    filename=filename,
                    model=model,
                    voice=voice
                ),
                timeout=180  # Increased to 3 minutes
            )
            
            # More detailed file validation
            if not os.path.exists(audio_path):
                console.print(f"[red]Expected audio file at: {audio_path}[/red]")
                console.print(f"[yellow]Directory contents: {os.listdir(os.path.dirname(audio_path))}[/yellow]")
                raise ValueError(f"Audio file not created at: {audio_path}")
                
            file_size = os.path.getsize(audio_path)
            if file_size < 100:  # Basic size check
                raise ValueError(f"Audio file suspiciously small: {file_size} bytes")
                
            console.print(f"[green]✓ Audio generated successfully: {audio_path} ({file_size} bytes)[/green]")
            return audio_path
            
        except asyncio.TimeoutError:
            console.print("[red]Audio generation timed out. Check if the TTS service is responding.[/red]")
            raise TimeoutError("Audio generation timed out after 180 seconds")
        
    except Exception as e:
        console.print("\n[red]Audio Generation Error Details:[/red]")
        console.print(f"[red]Error type: {type(e).__name__}[/red]")
        console.print(f"[red]Error message: {str(e)}[/red]")
        
        # Enhanced debug information
        console.print("\n[yellow]Debug State:[/yellow]")
        console.print(f"- Model: {model if 'model' in locals() else 'Not set'}")
        console.print(f"- Voice: {voice if 'voice' in locals() else 'Not set'}")
        console.print(f"- Working directory: {os.getcwd()}")
        console.print(f"- Script length: {len(script) if 'script' in locals() else 'Not available'}")
        console.print(f"- Available files: {os.listdir('.')}")
        
        raise

async def generate_video(video_generator: VideoGenerator, audio_path: str, content: dict, progress: Progress) -> str:
    """Generate video with audio and content"""
    try:
        filename = f"youtube_shorts_{int(time.time())}"
        
        # Validate inputs before proceeding
        if not os.path.exists(audio_path):
            raise ValueError(f"Audio file not found at: {audio_path}")
        
        if not content or not isinstance(content, dict):
            raise ValueError(f"Invalid content format: {type(content)}")
            
        # Add detailed debug logging
        console.print("[yellow]Debug: Video Generation Steps:[/yellow]")
        console.print(f"[yellow]1. Audio path: {audio_path}[/yellow]")
        console.print(f"[yellow]2. Content keys: {list(content.keys())}[/yellow]")
        console.print(f"[yellow]3. Output filename: {filename}[/yellow]")
        
        task = progress.add_task("[cyan]Creating video...", total=300)
        
        # Add pre-generation checks
        video_generator.validate_dependencies()  # You'll need to implement this method
        
        video_path = await video_generator.generate_video(
            audio_path, 
            content, 
            filename,
            progress_callback=lambda step, percentage: update_progress(progress, step, percentage, task)
        )
        
        # Detailed validation of output
        if not video_path:
            raise ValueError("Video generation failed - empty path returned")
            
        if not os.path.exists(video_path):
            raise ValueError(f"Video file not created at: {video_path}")
            
        # Check file size to ensure it's not empty
        file_size = os.path.getsize(video_path)
        if file_size == 0:
            raise ValueError(f"Generated video file is empty: {video_path}")
            
        console.print(f"[green]✓ Video generated successfully ({file_size} bytes)[/green]")
        return video_path
        
    except Exception as e:
        console.print("\n[red]Video Generation Error Details:[/red]")
        console.print(f"[red]Error type: {type(e).__name__}[/red]")
        console.print(f"[red]Error message: {str(e)}[/red]")
        
        # Add system information
        console.print("\n[yellow]System Information:[/yellow]")
        console.print(f"- Working directory: {os.getcwd()}")
        console.print(f"- Python version: {sys.version.split()[0]}")
        
        raise RuntimeError(f"Video generation failed: {str(e)}") from e

def update_progress(progress, step: str, percentage: float, task_id: int):
    """Update progress bar based on the current step and percentage"""
    base_progress = {
        'compose': 0,
        'render': 100,
        'export': 200
    }
    
    # Calculate actual progress (each step is worth 100 units)
    actual_progress = base_progress[step] + percentage
    
    # Update description based on step
    descriptions = {
        'compose': "[cyan]Composing video frames...",
        'render': "[cyan]Rendering video...",
        'export': "[cyan]Exporting final video..."
    }
    
    progress.update(
        task_id, 
        completed=actual_progress,
        description=descriptions[step]
    )

def display_results(content: dict) -> None:
    """Display generated content in a formatted way"""
    console.print("\n[bold green]✨ Generated Content ✨[/bold green]\n")
    
    # Display Title
    console.print(Panel(
        f"📝 {content['title']}",
        title="[yellow]Title[/yellow]",
        border_style="yellow"
    ))
    
    # Display Script
    console.print(Panel(
        f"🎬 {content['script']}",
        title="[blue]Script[/blue]",
        border_style="blue"
    ))
    
    # Display Hashtags
    console.print(Panel(
        f"🏷️ " + " ".join(f"#{tag}" for tag in content['hashtags']),
        title="[green]Hashtags[/green]",
        border_style="green"
    ))

def save_content_to_file(content: dict, video_path: str, audio_path: str) -> str:
    """Save generated content to a text file in src/contents/script directory"""
    # Create directory if it doesn't exist
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
        # Add audio generation details
        f.write(f"Audio Model: {getattr(audio_generator, 'last_used_model', 'edge')}\n")
        f.write(f"Voice: {getattr(audio_generator, 'last_used_voice', 'default')}\n")
    
    return filepath

async def main():
    # Clear screen and show welcome message
    console.clear()
    console.print("[bold magenta]🎥 YouTube Shorts Content Generator 🎥[/bold magenta]\n")
    
    try:
        # Initialize all generators
        content_generator = ContentGenerator()
        audio_generator = AudioGenerator()
        video_generator = VideoGenerator()
        
        # Get user input
        idea = Prompt.ask("[cyan]💡 Enter your video idea[/cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
        ) as progress:
            # Content generation
            content_task = progress.add_task("[yellow]Generating content...", total=100)
            content = await generate_content(content_generator, idea)
            progress.update(content_task, completed=100)
            
            # Audio generation
            audio_task = progress.add_task("[blue]Generating audio...", total=100)
            audio_path = await generate_audio(audio_generator, content['script'])
            progress.update(audio_task, completed=100)
            
            # Video generation
            video_path = await generate_video(video_generator, audio_path, content, progress)

        # Display results including paths
        display_results(content)
        content_file = save_content_to_file(content, video_path, audio_path)
        console.print(Panel(
            f"🎵 Audio saved to: {audio_path}\n"
            f"🎥 Video saved to: {video_path}\n"
            f"📄 Content saved to: {content_file}",
            title="[purple]Generated Files[/purple]",
            border_style="purple"
        ))
        
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️ Operation cancelled by user[/yellow]")
        return 1
    except Exception as e:
        console.print(f"\n[red] An error occurred: {str(e)}[/red]")
        return 1
    
    return 0

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Run the main function
    exit_code = asyncio.run(main())
    exit(exit_code)

