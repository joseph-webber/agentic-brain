# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Cloud TTS Fallback

Provides cloud-based text-to-speech when local voice systems fail.
Supports multiple providers with automatic fallback:

1. Google TTS (gTTS) - FREE, no API key required
2. Azure Cognitive Services Speech (requires key)
3. AWS Polly (requires credentials)
4. ElevenLabs (requires API key)
"""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


async def speak_gtts(text: str, lang: str = "en") -> bool:
    """
    Speak using Google Text-to-Speech (gTTS).

    This is FREE and requires no API key, only internet connection.

    Args:
        text: Text to speak
        lang: Language code (default 'en' for English)

    Returns:
        True if successful
    """
    try:
        from gtts import gTTS

        # Generate speech in executor (blocking I/O)
        loop = asyncio.get_event_loop()

        def _generate():
            try:
                tts = gTTS(text=text, lang=lang)
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tts.save(f.name)
                    return f.name
            except Exception as e:
                logger.error(f"gTTS generation error: {e}")
                return None

        mp3_file = await loop.run_in_executor(None, _generate)
        if not mp3_file:
            return False

        # Play the audio file
        try:
            success = await _play_audio_file(mp3_file)
            return success
        finally:
            # Clean up temp file
            try:
                os.unlink(mp3_file)
            except Exception:
                pass

    except ImportError:
        logger.debug("gTTS not installed (pip install gTTS)")
        return False
    except Exception as e:
        logger.error(f"gTTS error: {e}")
        return False


async def speak_azure(text: str, voice: Optional[str] = None) -> bool:
    """
    Speak using Azure Cognitive Services Speech.

    Requires environment variables:
    - AZURE_SPEECH_KEY: Your Azure subscription key
    - AZURE_SPEECH_REGION: Your service region (e.g., 'eastus')

    Args:
        text: Text to speak
        voice: Voice name (e.g., 'en-US-JennyNeural')

    Returns:
        True if successful
    """
    speech_key = os.getenv("AZURE_SPEECH_KEY")
    speech_region = os.getenv("AZURE_SPEECH_REGION")

    if not speech_key or not speech_region:
        logger.debug("Azure Speech credentials not configured")
        return False

    try:
        import azure.cognitiveservices.speech as speechsdk

        # Configure speech
        speech_config = speechsdk.SpeechConfig(
            subscription=speech_key, region=speech_region
        )

        if voice:
            speech_config.speech_synthesis_voice_name = voice

        # Use default speaker
        audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)

        # Create synthesizer
        synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=speech_config, audio_config=audio_config
        )

        # Synthesize in executor
        loop = asyncio.get_event_loop()

        def _synthesize():
            result = synthesizer.speak_text_async(text).get()
            return result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted

        success = await loop.run_in_executor(None, _synthesize)
        return success

    except ImportError:
        logger.debug(
            "Azure Speech SDK not installed (pip install azure-cognitiveservices-speech)"
        )
        return False
    except Exception as e:
        logger.error(f"Azure Speech error: {e}")
        return False


async def speak_aws_polly(text: str, voice: Optional[str] = None) -> bool:
    """
    Speak using AWS Polly.

    Requires AWS credentials configured (boto3).

    Args:
        text: Text to speak
        voice: Voice ID (e.g., 'Joanna', 'Matthew')

    Returns:
        True if successful
    """
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        logger.debug("AWS credentials not configured")
        return False

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError

        # Create Polly client
        polly = boto3.client("polly")

        # Synthesize speech
        loop = asyncio.get_event_loop()

        def _synthesize():
            try:
                response = polly.synthesize_speech(
                    Text=text,
                    OutputFormat="mp3",
                    VoiceId=voice or "Joanna",
                    Engine="neural",  # Use neural engine for better quality
                )

                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(response["AudioStream"].read())
                    return f.name
            except (BotoCoreError, ClientError) as e:
                logger.error(f"Polly error: {e}")
                return None

        mp3_file = await loop.run_in_executor(None, _synthesize)
        if not mp3_file:
            return False

        # Play the audio
        try:
            success = await _play_audio_file(mp3_file)
            return success
        finally:
            try:
                os.unlink(mp3_file)
            except Exception:
                pass

    except ImportError:
        logger.debug("boto3 not installed (pip install boto3)")
        return False
    except Exception as e:
        logger.error(f"AWS Polly error: {e}")
        return False


async def _play_audio_file(file_path: str) -> bool:
    """
    Play an audio file using available system player.

    Tries players in order:
    1. afplay (macOS)
    2. mpg123 (Linux)
    3. ffplay (cross-platform)
    4. Windows Media Player (Windows)

    Args:
        file_path: Path to audio file

    Returns:
        True if played successfully
    """
    players = [
        ("afplay", []),  # macOS
        ("mpg123", ["-q"]),  # Linux
        ("mpg321", ["-q"]),  # Linux alternative
        ("ffplay", ["-nodisp", "-autoexit", "-loglevel", "quiet"]),  # Cross-platform
    ]

    for player, args in players:
        if shutil.which(player):
            try:
                cmd = [player] + args + [file_path]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
                return proc.returncode == 0
            except Exception as e:
                logger.debug(f"{player} error: {e}")
                continue

    # Windows fallback - use default player
    try:
        import platform

        if platform.system() == "Windows":
            import os

            os.startfile(file_path)
            # Wait a bit for playback (can't easily detect completion)
            await asyncio.sleep(3)
            return True
    except Exception as e:
        logger.debug(f"Windows player error: {e}")

    logger.error("No audio player available")
    return False


async def speak_cloud(
    text: str, provider: str = "auto", voice: Optional[str] = None, lang: str = "en"
) -> bool:
    """
    Speak using cloud TTS with automatic provider fallback.

    Tries providers in order:
    1. Google TTS (free, no key needed)
    2. Azure Speech (if configured)
    3. AWS Polly (if configured)

    Args:
        text: Text to speak
        provider: Provider name or 'auto' for automatic fallback
        voice: Voice name/ID (provider-specific)
        lang: Language code (for gTTS)

    Returns:
        True if any provider succeeded
    """
    if provider == "gtts":
        return await speak_gtts(text, lang)
    elif provider == "azure":
        return await speak_azure(text, voice)
    elif provider == "polly":
        return await speak_aws_polly(text, voice)

    # Auto mode - try all providers
    # Start with free option
    if await speak_gtts(text, lang):
        logger.info("Cloud TTS succeeded with Google TTS")
        return True

    # Try paid services if configured
    if await speak_azure(text, voice):
        logger.info("Cloud TTS succeeded with Azure Speech")
        return True

    if await speak_aws_polly(text, voice):
        logger.info("Cloud TTS succeeded with AWS Polly")
        return True

    logger.error("All cloud TTS providers failed")
    return False


def check_cloud_tts_available() -> dict:
    """
    Check which cloud TTS providers are available.

    Returns:
        Dict with availability status for each provider
    """
    return {
        "gtts": _check_gtts_available(),
        "azure": _check_azure_available(),
        "aws_polly": _check_aws_polly_available(),
    }


def _check_gtts_available() -> bool:
    """Check if gTTS is available"""
    try:
        from gtts import gTTS

        return True
    except ImportError:
        return False


def _check_azure_available() -> bool:
    """Check if Azure Speech is available"""
    if not os.getenv("AZURE_SPEECH_KEY"):
        return False
    try:
        import azure.cognitiveservices.speech

        return True
    except ImportError:
        return False


def _check_aws_polly_available() -> bool:
    """Check if AWS Polly is available"""
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        return False
    try:
        import boto3

        return True
    except ImportError:
        return False


if __name__ == "__main__":
    # Test cloud TTS
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("Cloud TTS Test")
        print("=" * 60)

        # Check availability
        print("\nProvider Availability:")
        availability = check_cloud_tts_available()
        for provider, available in availability.items():
            status = "✓ AVAILABLE" if available else "✗ Not configured"
            print(f"  {provider:15s}: {status}")

        # Test speech
        print("\nTesting cloud TTS...")
        text = "Hello! This is cloud text to speech working over the internet."
        success = await speak_cloud(text)

        if success:
            print("✓ Cloud TTS test successful!")
        else:
            print("✗ Cloud TTS test failed!")

    asyncio.run(test())
