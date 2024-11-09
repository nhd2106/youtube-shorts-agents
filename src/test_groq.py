import asyncio
from groq.types.chat import ChatCompletion
from groq import AsyncGroq
import os
from dotenv import load_dotenv

async def test_groq():
    load_dotenv()
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    
    response = await client.chat.completions.create(
        model="mixtral-8x7b-32768",
        messages=[{"role": "user", "content": "Say hello"}]
    )
    
    print(response.choices[0].message.content)

if __name__ == "__main__":
    asyncio.run(test_groq()) 