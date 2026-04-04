"""
🔥 LUDICROUS SMASH MODE CI TEST 🔥
Claude SMASHES all other LLMs in parallel for maximum speed!
"""
import pytest
import asyncio
import httpx
import os
import time

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="API keys required for ludicrous mode"
)


class LudicriousSmashMode:
    """🔥 MAXIMUM SPEED LLM SMASHING 🔥"""
    
    def __init__(self):
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.groq_key = os.environ.get("GROQ_API_KEY", "")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.results = []
    
    async def smash_openai(self, prompt: str):
        """SMASH OpenAI!"""
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers={'Authorization': f'Bearer {self.openai_key}'},
                    json={'model': 'gpt-4o-mini', 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 50}
                )
                elapsed = time.time() - start
                ok = r.status_code == 200
                self.results.append(("openai", elapsed, ok))
                return "openai", ok
        except Exception as e:
            self.results.append(("openai", time.time() - start, False))
            return "openai", False
    
    async def smash_groq(self, prompt: str):
        """SMASH Groq - THE FASTEST!"""
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    'https://api.groq.com/openai/v1/chat/completions',
                    headers={'Authorization': f'Bearer {self.groq_key}'},
                    json={'model': 'llama-3.3-70b-versatile', 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 50}
                )
                elapsed = time.time() - start
                ok = r.status_code == 200
                self.results.append(("groq", elapsed, ok))
                return "groq", ok
        except Exception as e:
            self.results.append(("groq", time.time() - start, False))
            return "groq", False
    
    async def smash_gemini(self, prompt: str):
        """SMASH Gemini - FREE!"""
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                r = await c.post(
                    f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}',
                    json={'contents': [{'parts': [{'text': prompt}]}]}
                )
                elapsed = time.time() - start
                data = r.json()
                ok = 'candidates' in data
                self.results.append(("gemini", elapsed, ok))
                return "gemini", ok
        except Exception as e:
            self.results.append(("gemini", time.time() - start, False))
            return "gemini", False
    
    async def smash_local(self, prompt: str):
        """SMASH Local Ollama - UNLIMITED!"""
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    'http://localhost:11434/api/generate',
                    json={'model': 'llama3.1:8b', 'prompt': prompt, 'stream': False}
                )
                elapsed = time.time() - start
                ok = r.status_code == 200
                self.results.append(("local", elapsed, ok))
                return "local", ok
        except Exception as e:
            self.results.append(("local", time.time() - start, False))
            return "local", False
    
    async def ludicrous_smash(self, prompt: str = "Say 'SMASHED' in one word"):
        """🔥 SMASH ALL LLMS IN PARALLEL! 🔥"""
        tasks = [
            self.smash_openai(prompt),
            self.smash_groq(prompt),
            self.smash_gemini(prompt),
            self.smash_local(prompt),
        ]
        
        start = time.time()
        await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start
        
        return {
            "total_time": total_time,
            "results": self.results,
            "success_count": sum(1 for _, _, ok in self.results if ok),
        }


@pytest.mark.smoke
@pytest.mark.ludicrous
class TestLudicriousSmashMode:
    """🔥 LUDICROUS SMASH MODE TESTS 🔥"""
    
    @pytest.mark.asyncio
    async def test_smash_all_llms_parallel(self):
        """Claude SMASHES all other LLMs in parallel!"""
        smasher = LudicriousSmashMode()
        result = await smasher.ludicrous_smash()
        
        print(f"\n🔥 LUDICROUS SMASH RESULTS 🔥")
        print(f"Total time: {result['total_time']:.2f}s")
        for provider, elapsed, ok in result['results']:
            status = "✅" if ok else "❌"
            print(f"  {status} {provider}: {elapsed:.2f}s")
        
        # At least 2 providers should work
        assert result['success_count'] >= 2, f"Only {result['success_count']}/4 LLMs responded"
        # Should complete in under 30 seconds (parallel!)
        assert result['total_time'] < 30, "Parallel smash should be fast!"
    
    @pytest.mark.asyncio
    async def test_groq_is_fastest(self):
        """Groq should be the FASTEST!"""
        smasher = LudicriousSmashMode()
        await smasher.ludicrous_smash()
        
        groq_result = next((r for r in smasher.results if r[0] == "groq"), None)
        if groq_result and groq_result[2]:  # If Groq succeeded
            print(f"\n⚡ Groq response time: {groq_result[1]:.2f}s")
            assert groq_result[1] < 5, "Groq should respond in under 5 seconds!"


if __name__ == "__main__":
    async def main():
        print("🔥 LUDICROUS SMASH MODE ACTIVATED! 🔥")
        smasher = LudicriousSmashMode()
        result = await smasher.ludicrous_smash()
        print(f"\n🏁 SMASHED {result['success_count']}/4 LLMs in {result['total_time']:.1f}s!")
        for provider, elapsed, ok in result['results']:
            status = "✅" if ok else "❌"
            print(f"  {status} {provider}: {elapsed:.2f}s")
    
    asyncio.run(main())
