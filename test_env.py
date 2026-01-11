"""
Quick test to check if environment variables are loading correctly.
Run this from the backend directory: python test_env.py
"""
import os
import sys
from dotenv import load_dotenv

# Fix Windows encoding issues
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("ENVIRONMENT VARIABLE TEST")
print("=" * 60)

# Check env vars BEFORE loading .env
print("\n1. BEFORE load_dotenv():")
print(f"   GROQ_API_KEY: {os.getenv('GROQ_API_KEY')[:20] if os.getenv('GROQ_API_KEY') else '[X] NOT SET'}")
print(f"   GOOGLE_AI_API_KEY: {os.getenv('GOOGLE_AI_API_KEY')[:20] if os.getenv('GOOGLE_AI_API_KEY') else '[X] NOT SET'}")

# Load .env file
print("\n2. Loading .env file...")
load_dotenv()

# Check env vars AFTER loading .env
print("\n3. AFTER load_dotenv():")
groq_key = os.getenv('GROQ_API_KEY')
google_key = os.getenv('GOOGLE_AI_API_KEY')

if groq_key:
    print(f"   [OK] GROQ_API_KEY: {groq_key[:20]}... (length: {len(groq_key)})")
else:
    print("   [X] GROQ_API_KEY: NOT FOUND")

if google_key:
    print(f"   [OK] GOOGLE_AI_API_KEY: {google_key[:20]}... (length: {len(google_key)})")
else:
    print("   [X] GOOGLE_AI_API_KEY: NOT FOUND")

# Test LLM Router initialization
print("\n4. Testing LLMRouter initialization:")
try:
    from app.core.llm_router import LLMRouter
    router = LLMRouter()
    print("   LLMRouter instantiated successfully")

    providers = []
    if router.groq:
        providers.append("Groq")
    if router.gemini:
        providers.append("Gemini")
    if router.bedrock:
        providers.append("Bedrock")

    if providers:
        print(f"   [OK] Active providers: {providers}")
    else:
        print("   [X] NO PROVIDERS CONFIGURED")

except Exception as e:
    print(f"   [X] ERROR: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
