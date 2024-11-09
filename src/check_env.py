import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")
print(f"API Key found: {'Yes' if api_key else 'No'}") 