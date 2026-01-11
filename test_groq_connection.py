"""
Test script to verify Groq API is working and making actual calls.

Run this from the backend directory:
    python test_groq_connection.py

OR with poetry:
    poetry run python test_groq_connection.py
"""
import os
import sys
import asyncio
from dotenv import load_dotenv

# Fix Windows encoding issues
sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

print("=" * 70)
print("GROQ API CONNECTION TEST")
print("=" * 70)

# Step 1: Check if API key is loaded
print("\n[Step 1] Checking environment variable...")
groq_key = os.getenv('GROQ_API_KEY')
if groq_key:
    print(f"   ✓ GROQ_API_KEY found: {groq_key[:15]}... (length: {len(groq_key)})")
else:
    print("   ✗ GROQ_API_KEY not found!")
    print("\n   Please add GROQ_API_KEY to your .env file")
    print("   Get a free key from: https://console.groq.com")
    sys.exit(1)

# Step 2: Initialize LLM Router
print("\n[Step 2] Initializing LLM Router...")
try:
    from app.core.llm_router import LLMRouter
    router = LLMRouter()

    if router.groq:
        print("   ✓ LLM Router initialized with Groq")
    else:
        print("   ✗ Groq client not initialized!")
        print("   Check if the groq package is installed: pip install groq")
        sys.exit(1)
except Exception as e:
    print(f"   ✗ Error initializing LLM Router: {e}")
    sys.exit(1)

# Step 3: Make actual API call to Groq
print("\n[Step 3] Making test API call to Groq...")
print("   (This will show up in your Groq dashboard at console.groq.com)")
print()

async def test_groq_call():
    """Make a real API call to Groq and verify response."""
    try:
        response_text, metadata = await router.generate(
            agent_role='annie',
            prompt='Say "Hello! I am Llama 4 Scout running on Groq." Then tell me what 2+2 equals.',
            system_prompt='You are Annie, an AI dispatcher. Respond briefly and confirm your model name.',
            temperature=0.7,
            max_tokens=150
        )

        print("   ✓ API CALL SUCCESSFUL!")
        print()
        print("-" * 70)
        print("RESPONSE FROM GROQ:")
        print("-" * 70)
        print(response_text)
        print("-" * 70)
        print()
        print("METADATA:")
        print(f"   Model: {metadata.get('model', 'N/A')}")
        print(f"   Provider: {metadata.get('provider', 'N/A')}")
        print(f"   Input Tokens: {metadata.get('input_tokens', 'N/A')}")
        print(f"   Output Tokens: {metadata.get('output_tokens', 'N/A')}")
        print(f"   Total Tokens: {metadata.get('tokens_used', 'N/A')}")
        print(f"   Cost: ${metadata.get('cost_usd', 0):.6f}")
        print()
        print("=" * 70)
        print("✓ SUCCESS! Groq is working and API calls are being made.")
        print("  Check your Groq dashboard to see this request logged.")
        print("=" * 70)

    except Exception as e:
        print(f"   ✗ API call failed: {e}")
        print()
        print("TROUBLESHOOTING:")
        print("1. Verify your API key is correct at console.groq.com")
        print("2. Check if you have rate limit remaining (14,400 requests/day free)")
        print("3. Ensure groq package is installed: pip install groq")
        print(f"4. Full error: {type(e).__name__}: {str(e)}")
        sys.exit(1)

# Run the test
try:
    asyncio.run(test_groq_call())
except KeyboardInterrupt:
    print("\n\nTest interrupted by user.")
    sys.exit(0)
except Exception as e:
    print(f"\n✗ Unexpected error: {e}")
    sys.exit(1)
