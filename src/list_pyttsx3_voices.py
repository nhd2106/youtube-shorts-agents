import pyttsx3

def print_voice_info(voice):
    print(f"ID: {voice.id}")
    print(f"Name: {voice.name}")
    print(f"Languages: {voice.languages}")
    print(f"Gender: {voice.gender}")
    print(f"Age: {voice.age}")
    print("---")

def main():
    try:
        # Initialize the pyttsx3 engine
        engine = pyttsx3.init()
        
        # Get current voice
        current_voice = engine.getProperty('voice')
        print("Current voice:")
        print_voice_info(current_voice)
        
        # Get all voices
        voices = engine.getProperty('voices')
        for voice in voices:
            print_voice_info(voice)
            
        # Try to say something in Vietnamese
        test_text = "Xin chào, tôi là giọng nói tiếng Việt"
        print("\nTesting Vietnamese text:")
        print(f"Text to speak: {test_text}")
        engine.setProperty('voice', 'MTTS_V110_viVN_An')
        engine.say(test_text)
        engine.runAndWait()
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if 'engine' in locals():
            engine.stop()

if __name__ == "__main__":
    main()
