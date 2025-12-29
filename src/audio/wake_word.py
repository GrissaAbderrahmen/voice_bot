"""
Wake word detection using Porcupine.
Listens for "Hey Nova" in the background.
"""

import struct
import threading
import time
from typing import Optional, Callable
import numpy as np
import sounddevice as sd

from ..core.logger import get_logger
from ..core.config import Config

logger = get_logger("nova.audio.wakeword")

# Try to import Porcupine
try:
    import pvporcupine
    HAS_PORCUPINE = True
except ImportError:
    HAS_PORCUPINE = False
    logger.warning("Porcupine not installed. Wake word detection disabled.")


class WakeWordDetector:
    """
    Wake word detector using Picovoice Porcupine.
    Falls back to push-to-talk if Porcupine is not available.
    """
    
    BUILT_IN_KEYWORDS = [
        "alexa", "americano", "blueberry", "bumblebee", "computer",
        "grapefruit", "grasshopper", "hey google", "hey siri", "jarvis",
        "ok google", "picovoice", "porcupine", "terminator"
    ]
    
    def __init__(
        self,
        access_key: Optional[str] = None,
        keyword: str = "computer",  # Built-in fallback
        sensitivity: float = 0.5,
        device: Optional[int] = None
    ):
        """
        Initialize wake word detector.
        
        Args:
            access_key: Picovoice access key (get free at console.picovoice.ai)
            keyword: Wake word to detect (use built-in or custom)
            sensitivity: Detection sensitivity 0-1 (higher = more false positives)
            device: Audio input device index
        """
        self.access_key = access_key
        self.keyword = keyword
        self.sensitivity = sensitivity
        self.device = device
        
        self._porcupine = None
        self._is_listening = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[], None]] = None
        self._stop_event = threading.Event()
        
        # Check if Porcupine is available
        if not HAS_PORCUPINE:
            logger.warning("Wake word detection unavailable. Using push-to-talk mode.")
            return
        
        if not access_key:
            logger.warning("No Porcupine access key. Get free key at console.picovoice.ai")
            logger.warning("Falling back to push-to-talk mode.")
            return
        
        self._init_porcupine()
    
    def _init_porcupine(self) -> None:
        """Initialize Porcupine engine."""
        try:
            # Use built-in keyword
            keyword_to_use = self.keyword.lower().replace(" ", "_")
            
            if keyword_to_use in [k.replace(" ", "_") for k in self.BUILT_IN_KEYWORDS]:
                self._porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=[self.keyword],
                    sensitivities=[self.sensitivity]
                )
                logger.info(f"✅ Wake word detector initialized: '{self.keyword}'")
            else:
                # For custom keywords, need keyword file
                logger.warning(f"Custom keyword '{self.keyword}' requires a .ppn file")
                logger.warning("Using 'computer' as fallback wake word")
                self._porcupine = pvporcupine.create(
                    access_key=self.access_key,
                    keywords=["computer"],
                    sensitivities=[self.sensitivity]
                )
                
        except Exception as e:
            logger.error(f"Failed to initialize Porcupine: {e}")
            self._porcupine = None
    
    @property
    def is_available(self) -> bool:
        """Check if wake word detection is available."""
        return self._porcupine is not None
    
    def start(self, on_wake: Callable[[], None]) -> None:
        """
        Start listening for wake word in background.
        
        Args:
            on_wake: Callback function when wake word is detected
        """
        if not self.is_available:
            logger.warning("Wake word detection not available")
            return
        
        if self._is_listening:
            logger.warning("Already listening for wake word")
            return
        
        self._callback = on_wake
        self._stop_event.clear()
        self._is_listening = True
        
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info("👂 Listening for wake word...")
    
    def _listen_loop(self) -> None:
        """Background thread for wake word detection."""
        try:
            frame_length = self._porcupine.frame_length
            sample_rate = self._porcupine.sample_rate
            
            def audio_callback(indata, frames, time_info, status):
                if self._stop_event.is_set():
                    raise sd.CallbackAbort()
                
                # Convert to int16
                audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
                
                # Process with Porcupine
                keyword_index = self._porcupine.process(audio_int16)
                
                if keyword_index >= 0:
                    logger.info("🎯 Wake word detected!")
                    if self._callback:
                        self._callback()
            
            with sd.InputStream(
                device=self.device,
                channels=1,
                samplerate=sample_rate,
                blocksize=frame_length,
                dtype=np.float32,
                callback=audio_callback
            ):
                while not self._stop_event.is_set():
                    time.sleep(0.1)
                    
        except Exception as e:
            if not self._stop_event.is_set():
                logger.error(f"Wake word detection error: {e}")
        finally:
            self._is_listening = False
    
    def stop(self) -> None:
        """Stop listening for wake word."""
        self._stop_event.set()
        self._is_listening = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        
        logger.debug("Wake word detection stopped")
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        if self._porcupine:
            self._porcupine.delete()
            self._porcupine = None
    
    def __del__(self):
        self.cleanup()


class PushToTalk:
    """
    Fallback for when wake word is not available.
    User presses Enter to start recording.
    """
    
    def __init__(self):
        self._waiting = False
        self._callback: Optional[Callable[[], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def start(self, on_activate: Callable[[], None]) -> None:
        """Start waiting for Enter key press."""
        self._callback = on_activate
        self._waiting = True
        self._stop_event.clear()
        
        self._thread = threading.Thread(target=self._wait_loop, daemon=True)
        self._thread.start()
        logger.info("⌨️ Press Enter to speak (push-to-talk mode)")
    
    def _wait_loop(self) -> None:
        """Wait for keyboard input."""
        while not self._stop_event.is_set():
            try:
                input()  # Wait for Enter
                if self._callback and self._waiting:
                    self._callback()
            except EOFError:
                break
    
    def stop(self) -> None:
        """Stop waiting."""
        self._stop_event.set()
        self._waiting = False
