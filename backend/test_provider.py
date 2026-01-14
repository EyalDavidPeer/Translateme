"""Direct test of the OpenAI provider."""
import os
import asyncio

# Set environment variables
# Load API key from environment or .env file
# os.environ["OPENAI_API_KEY"] = "your-api-key-here"
os.environ["TRANSLATION_PROVIDER"] = "openai"

from app.models import SubtitleSegment, JobConstraints
from app.translation import OpenAIProvider

async def main():
    print("Testing OpenAI Provider directly...")
    
    # Create provider
    try:
        provider = OpenAIProvider()
        print(f"Provider created: {provider.get_provider_name()}")
        print(f"Model: {provider.model}")
    except Exception as e:
        print(f"ERROR creating provider: {e}")
        return
    
    # Create test segments
    segments = [
        SubtitleSegment(index=1, start_ms=0, end_ms=3000, text="Hello, welcome to our show!"),
        SubtitleSegment(index=2, start_ms=3500, end_ms=6000, text="Today we will discuss technology."),
    ]
    
    constraints = JobConstraints()
    
    print("\nTranslating to Hebrew...")
    try:
        result = await provider.translate_batch(
            segments=segments,
            context_window=[],
            source_lang="en",
            target_lang="he",
            glossary={},
            constraints=constraints
        )
        
        print("\nResults saved to test_output.txt")
        with open("test_output.txt", "w", encoding="utf-8") as f:
            for seg in result:
                f.write(f"#{seg.index}: {seg.text}\n")
                f.write(f"  => {seg.translated_text}\n\n")
            
    except Exception as e:
        print(f"ERROR during translation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
