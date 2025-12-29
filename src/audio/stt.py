"""
Speech-to-Text using local OpenAI Whisper.
Runs entirely on your machine - no API calls, completely free.
"""

import io
import tempfile
import os
from pathlib import Path
from typing import Optional, Tuple
import numpy as np

from ..core.logger import get_logger

logger = get_logger("nova.audio.stt")

# Lazy import whisper (it's heavy)
_whisper_model = None


def _load_whisper(model_name: str = "base", device: str = "cpu"):
    """Load Whisper model (lazy loading to speed up startup)."""
    global _whisper_model
    
    if _whisper_model is None:
        logger.info(f"Loading Whisper model '{model_name}'... (first time may take a minute)")
        
        try:
            import whisper
            _whisper_model = whisper.load_model(model_name, device=device)
            logger.info(f"✅ Whisper model loaded on {device}")
        except Exception as e:
            logger.error(f"Failed to load Whisper: {e}")
            raise
    
    return _whisper_model


class SpeechToText:
    """
    Speech-to-text using local Whisper model.
    Supports multiple languages and auto-detection.
    """
    
    SUPPORTED_LANGUAGES = {
        "en": "english",
        "fr": "french",
        "es": "spanish",
        "de": "german",
        "it": "italian",
        "pt": "portuguese",
        "nl": "dutch",
        "pl": "polish",
        "ru": "russian",
        "zh": "chinese",
        "ja": "japanese",
        "ko": "korean",
        "ar": "arabic"
    }
    
    def __init__(
        self,
        model: str = "base",
        device: str = "cpu",
        languages: Optional[list] = None
    ):
        """
        Initialize Speech-to-Text.
        
        Args:
            model: Whisper model size (tiny, base, small, medium, large)
            device: Device to run on ("cpu" or "cuda")
            languages: List of language codes to detect (None = auto-detect all)
        """
        self.model_name = model
        self.device = device
        self.languages = languages or ["en", "fr"]
        
        # Model is loaded lazily on first use
        self._model = None
        
        logger.debug(f"STT initialized: model={model}, device={device}")
    
    def _ensure_model(self):
        """Ensure Whisper model is loaded."""
        if self._model is None:
            self._model = _load_whisper(self.model_name, self.device)
        return self._model
    
    def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        Transcribe audio to text.
        
        Args:
            audio_data: WAV audio data as bytes
            language: Force specific language (None = auto-detect)
        
        Returns:
            Tuple of (transcription, detected_language_code)
        """
        model = self._ensure_model()
        
        # Save to temp file (Whisper needs file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            logger.debug("Transcribing audio...")
            
            # Transcribe
            options = {
                "fp16": False,  # CPU doesn't support fp16
            }
            
            if language:
                options["language"] = language
            
            result = model.transcribe(temp_path, **options)
            
            text = result["text"].strip()
            detected_lang = result.get("language", "en")
            
            logger.info(f"📝 Transcribed ({detected_lang}): {text[:50]}...")
            
            return text, detected_lang
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return "", "en"
            
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except:
                pass
    
    def transcribe_file(self, file_path: str) -> Tuple[str, str]:
        """
        Transcribe audio from file.
        
        Args:
            file_path: Path to audio file (WAV, MP3, etc.)
        
        Returns:
            Tuple of (transcription, detected_language_code)
        """
        model = self._ensure_model()
        
        try:
            logger.debug(f"Transcribing file: {file_path}")
            
            result = model.transcribe(file_path, fp16=False)
            
            text = result["text"].strip()
            detected_lang = result.get("language", "en")
            
            logger.info(f"📝 Transcribed ({detected_lang}): {text[:50]}...")
            
            return text, detected_lang
            
        except Exception as e:
            logger.error(f"File transcription failed: {e}")
            return "", "en"
    
    def detect_language(self, audio_data: bytes) -> str:
        """
        Detect language of audio without full transcription.
        
        Args:
            audio_data: WAV audio data as bytes
        
        Returns:
            Detected language code (e.g., "en", "fr")
        """
        model = self._ensure_model()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name
        
        try:
            import whisper
            
            # Load audio
            audio = whisper.load_audio(temp_path)
            audio = whisper.pad_or_trim(audio)
            
            # Make log-Mel spectrogram
            mel = whisper.log_mel_spectrogram(audio).to(model.device)
            
            # Detect language
            _, probs = model.detect_language(mel)
            detected = max(probs, key=probs.get)
            
            logger.debug(f"Detected language: {detected}")
            return detected
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return "en"
            
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass
    
    @staticmethod
    def list_models() -> list:
        """List available Whisper models."""
        return [
            {"name": "tiny", "size": "39M", "speed": "fastest", "accuracy": "lowest"},
            {"name": "base", "size": "74M", "speed": "fast", "accuracy": "good"},
            {"name": "small", "size": "244M", "speed": "medium", "accuracy": "better"},
            {"name": "medium", "size": "769M", "speed": "slow", "accuracy": "high"},
            {"name": "large", "size": "1550M", "speed": "slowest", "accuracy": "highest"},
        ]
