"""List available Gemini models."""
import os
from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai

genai.configure(api_key=os.getenv("GOOGLE_AI_API_KEY"))

print("Available Gemini models:")
print("=" * 60)

for model in genai.list_models():
    if 'generateContent' in model.supported_generation_methods:
        print(f"\nModel: {model.name}")
        print(f"  Display name: {model.display_name}")
        print(f"  Description: {model.description[:100]}..." if len(model.description) > 100 else f"  Description: {model.description}")
