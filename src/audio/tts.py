"""
Text-to-Speech using Microsoft Edge TTS.
Free, high-quality neural voices with streaming support.
"""

import asyncio
import io
import tempfile
import os
from pathlib import Path
from typing import Optional, List, AsyncGenerator
import threading
import queue

from ..core.logger import get_logger

logger = get_logger("nova.audio.tts")

# Try to import dependencies
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    logger.warning("edge-tts not installed. TTS will not work.")

try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except Exception as e:
    HAS_PYGAME = False
    logger.warning(f"pygame audio not available: {e}")


class TextToSpeech:
    """
    Text-to-speech using Microsoft Edge TTS.
    Supports multiple voices, languages, and streaming.
    """
    
    # Popular voice options
    VOICES = {
        # English
        "en-US-AriaNeural": "English (US) - Aria (Female)",
        "en-US-GuyNeural": "English (US) - Guy (Male)",
        "en-US-JennyNeural": "English (US) - Jenny (Female)",
        "en-GB-SoniaNeural": "English (UK) - Sonia (Female)",
        "en-GB-RyanNeural": "English (UK) - Ryan (Male)",
        # French
        "fr-FR-DeniseNeural": "French - Denise (Female)",
        "fr-FR-HenriNeural": "French - Henri (Male)",
        # Other languages
        "es-ES-ElviraNeural": "Spanish - Elvira (Female)",
        "de-DE-KatjaNeural": "German - Katja (Female)",
        "it-IT-ElsaNeural": "Italian - Elsa (Female)",
    }
    
    def __init__(
        self,
        voice_en: str = "en-US-AriaNeural",
        voice_fr: str = "fr-FR-DeniseNeural",
        rate: str = "+0%",
        volume: str = "+0%"
    ):
        """
        Initialize TTS engine.
        
        Args:
            voice_en: Voice for English
            voice_fr: Voice for French
            rate: Speech rate adjustment (-50% to +50%)
            volume: Volume adjustment (-50% to +50%)
        """
        self.voice_en = voice_en
        self.voice_fr = voice_fr
        self.rate = rate
        self.volume = volume
        
        self._is_speaking = False
        self._stop_event = threading.Event()
        self._current_sound = None
        
        if not HAS_EDGE_TTS:
            logger.error("edge-tts is required for TTS")
        
        logger.debug(f"TTS initialized: en={voice_en}, fr={voice_fr}")
    
    def get_voice_for_language(self, lang: str) -> str:
        """Get appropriate voice for detected language."""
        if lang.startswith("fr"):
            return self.voice_fr
        else:
            return self.voice_en
    
    async def synthesize(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesize text to audio.
        
        Args:
            text: Text to speak
            voice: Voice to use (None = use default English voice)
        
        Returns:
            MP3 audio data as bytes
        """
        if not HAS_EDGE_TTS:
            logger.error("edge-tts not available")
            return b""
        
        voice = voice or self.voice_en
        
        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=self.rate,
                volume=self.volume
            )
            
            # Collect all audio chunks
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            
            return b"".join(audio_chunks)
            
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return b""
    
    async def speak(
        self,
        text: str,
        lang: str = "en",
        wait: bool = True
    ) -> None:
        """
        Speak text out loud.
        
        Args:
            text: Text to speak
            lang: Language code (determines voice)
            wait: Whether to wait for speech to complete
        """
        if not HAS_PYGAME:
            logger.error("pygame not available for audio playback")
            return
        
        voice = self.get_voice_for_language(lang)
        logger.info(f"🔊 Speaking ({lang}): {text[:50]}...")
        
        # Synthesize
        audio_data = await self.synthesize(text, voice)
        
        if not audio_data:
            return
        
        # Play audio
        self._stop_event.clear()
        self._is_speaking = True
        
        try:
            # Save to temp file for pygame
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_data)
                temp_path = f.name
            
            # Play with pygame
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            
            if wait:
                while pygame.mixer.music.get_busy() and not self._stop_event.is_set():
                    await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Audio playback failed: {e}")
        finally:
            self._is_speaking = False
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def speak_sync(self, text: str, lang: str = "en", wait: bool = True) -> None:
        """Synchronous wrapper for speak()."""
        asyncio.run(self.speak(text, lang, wait))
    
    async def speak_streaming(
        self,
        text_generator: AsyncGenerator[str, None],
        lang: str = "en"
    ) -> None:
        """
        Speak text as it's generated (for streaming LLM responses).
        
        Args:
            text_generator: Async generator yielding text chunks
            lang: Language code
        """
        buffer = ""
        sentence_endings = ".!?;"
        
        async for chunk in text_generator:
            buffer += chunk
            
            # Check if we have a complete sentence
            for i, char in enumerate(buffer):
                if char in sentence_endings:
                    sentence = buffer[:i+1].strip()
                    buffer = buffer[i+1:]
                    
                    if sentence:
                        await self.speak(sentence, lang, wait=True)
                        
                        if self._stop_event.is_set():
                            return
                    break
        
        # Speak remaining buffer
        if buffer.strip():
            await self.speak(buffer.strip(), lang, wait=True)
    
    def stop(self) -> None:
        """Stop current speech."""
        self._stop_event.set()
        
        try:
            pygame.mixer.music.stop()
        except:
            pass
        
        self._is_speaking = False
        logger.debug("TTS stopped")
    
    @property
    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._is_speaking
    
    @staticmethod
    async def list_voices(language: Optional[str] = None) -> List[dict]:
        """
        List all available Edge TTS voices.
        
        Args:
            language: Filter by language code (e.g., "en", "fr")
        
        Returns:
            List of voice info dicts
        """
        if not HAS_EDGE_TTS:
            return []
        
        try:
            voices = await edge_tts.list_voices()
            
            if language:
                voices = [v for v in voices if v["Locale"].startswith(language)]
            
            return [
                {
                    "name": v["ShortName"],
                    "gender": v["Gender"],
                    "locale": v["Locale"],
                    "friendly_name": v["FriendlyName"]
                }
                for v in voices
            ]
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
    
    @staticmethod
    def list_voices_sync(language: Optional[str] = None) -> List[dict]:
        """Synchronous wrapper for list_voices()."""
        return asyncio.run(TextToSpeech.list_voices(language))


async def demo_voice(voice_name: str, text: str = "Hello! This is a voice demo.") -> None:
    """Play a demo of a specific voice."""
    tts = TextToSpeech(voice_en=voice_name)
    await tts.speak(text, "en")
