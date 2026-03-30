#!/usr/bin/env python3
"""
Voice Handler - Bridge between native Swift app and agentic-brain
Reads prompt from file, processes with Claude, writes response
"""
import sys
import os

def main():
    if len(sys.argv) < 3:
        print("Usage: voice_handler.py <prompt_file> <response_file>")
        sys.exit(1)
    
    prompt_file = sys.argv[1]
    response_file = sys.argv[2]
    
    # Read prompt
    try:
        with open(prompt_file, 'r') as f:
            prompt = f.read().strip()
    except Exception as e:
        with open(response_file, 'w') as f:
            f.write(f"Error reading prompt: {e}")
        sys.exit(1)
    
    if not prompt:
        with open(response_file, 'w') as f:
            f.write("No prompt received")
        sys.exit(0)
    
    # Try to use Claude via anthropic SDK
    try:
        import anthropic
        client = anthropic.Anthropic()
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system="You are Karen, Joseph's AI assistant. Keep responses SHORT (1-2 sentences) for voice output. Joseph is blind so be clear and helpful.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = response.content[0].text
        
    except ImportError:
        # Fallback: echo back
        answer = f"I heard: {prompt}. Claude SDK not available."
    except Exception as e:
        answer = f"Error processing: {str(e)[:100]}"
    
    # Write response
    with open(response_file, 'w') as f:
        f.write(answer)

if __name__ == "__main__":
    main()
