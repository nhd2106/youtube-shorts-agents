# -*- coding: utf-8 -*-
import asyncio
import os
from dotenv import load_dotenv
from content_generator import ContentGenerator

async def main():
    print("=== YouTube Shorts Content Generator ===\n")
    
    # Initialize the generator
    generator = ContentGenerator()
    
    # Simple input
    print("Enter your video idea:")
    idea = input()
    print(f"You entered: {idea}")  # Debug line
    
    try:
        # Generate content
        print("\nGenerating content...")
        content = await generator.generate_content(idea)
        
        # Print results
        print("\n=== Generated Content ===")
        print(f"\nTitle: {content['title']}")
        print(f"\nScript: {content['script']}")
        print(f"\nHashtags: {', '.join(content['hashtags'])}")
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main())