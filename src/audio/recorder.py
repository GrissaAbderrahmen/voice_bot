"""
Audio recording with Voice Activity Detection.
Records from microphone and auto-stops on silence.
"""

import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad
import io
import wave
from pathlib import Path
from typing import Optional, Tuple, List, Callable
from collections import deque
import threading
import time

from ..core.logger import get_logger

logger = get_logger("nova.audio.recorder")


class AudioRecorder:
    """
    Records audio from microphone with Voice Activity Detection.
    Automatically stops recording after detecting silence.
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        frame_duration_ms: int = 30,
        silence_duration: float = 1.5,
        vad_aggressiveness: int = 2,
        device: Optional[int] = None
    ):
        """
        Initialize the audio recorder.
        
        Args:
            sample_rate: Audio sample rate (16000 recommended for Whisper)
            channels: Number of audio channels (1 = mono)
            frame_duration_ms: VAD frame duration (10, 20, or 30 ms)
            silence_duration: Seconds of silence to stop recording
            vad_aggressiveness: VAD sensitivity 0-3 (higher = more sensitive)
            device: Specific audio device index (None = default)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.frame_duration_ms = frame_duration_ms
        self.silence_duration = silence_duration
        self.device = device
        
        # VAD setup
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        
        # Calculate frame size in samples
        self.frame_size = int(sample_rate * frame_duration_ms / 1000)
        
        # Recording state
        self._is_recording = False
        self._audio_buffer: List[bytes] = []
        self._level_callback: Optional[Callable[[float], None]] = None
        
        logger.debug(f"AudioRecorder initialized: {sample_rate}Hz, VAD={vad_aggressiveness}")
    
    @staticmethod
    def list_devices() -> List[dict]:
        """List available audio input devices."""
        devices = []
        for i, device in enumerate(sd.query_devices()):
            if device['max_input_channels'] > 0:
                devices.append({
                    'index': i,
                    'name': device['name'],
                    'channels': device['max_input_channels'],
                    'sample_rate': device['default_samplerate']
                })
        return devices
    
    @staticmethod
    def get_default_device() -> Optional[dict]:
        """Get the default input device info."""
        try:
            device_id = sd.default.device[0]
            if device_id is not None:
                device_info = sd.query_devices(device_id)
                return {
                    'index': device_id,
                    'name': device_info['name'],
                    'channels': device_info['max_input_channels']
                }
        except Exception as e:
            logger.warning(f"Could not get default device: {e}")
        return None
    
    def set_level_callback(self, callback: Callable[[float], None]) -> None:
        """Set a callback to receive audio level updates (0.0 - 1.0)."""
        self._level_callback = callback
    
    def record(
        self,
        max_duration: float = 30.0,
        on_speech_start: Optional[Callable[[], None]] = None,
        on_speech_end: Optional[Callable[[], None]] = None
    ) -> Optional[bytes]:
        """
        Record audio until silence is detected or max duration reached.
        
        Args:
            max_duration: Maximum recording duration in seconds
            on_speech_start: Callback when speech is detected
            on_speech_end: Callback when recording ends
        
        Returns:
            WAV audio data as bytes, or None if cancelled
        """
        if self._is_recording:
            logger.warning("Already recording")
            return None
        
        self._is_recording = True
        self._audio_buffer = []
        
        # Tracking for VAD
        speech_started = False
        silence_frames = 0
        frames_for_silence = int(self.silence_duration * 1000 / self.frame_duration_ms)
        max_frames = int(max_duration * 1000 / self.frame_duration_ms)
        frame_count = 0
        
        logger.info("🎤 Recording started...")
        
        try:
            def audio_callback(indata, frames, time_info, status):
                nonlocal speech_started, silence_frames, frame_count
                
                if status:
                    logger.warning(f"Audio status: {status}")
                
                if not self._is_recording:
                    raise sd.CallbackAbort()
                
                # Convert to bytes for VAD
                audio_int16 = (indata[:, 0] * 32767).astype(np.int16)
                audio_bytes = audio_int16.tobytes()
                
                # Calculate audio level
                level = np.abs(indata).mean()
                if self._level_callback:
                    self._level_callback(min(level * 10, 1.0))
                
                # VAD check
                try:
                    is_speech = self.vad.is_speech(audio_bytes, self.sample_rate)
                except Exception:
                    is_speech = level > 0.01  # Fallback to simple threshold
                
                if is_speech:
                    if not speech_started:
                        speech_started = True
                        logger.debug("Speech detected")
                        if on_speech_start:
                            on_speech_start()
                    silence_frames = 0
                    self._audio_buffer.append(audio_bytes)
                elif speech_started:
                    silence_frames += 1
                    self._audio_buffer.append(audio_bytes)
                    
                    if silence_frames >= frames_for_silence:
                        logger.debug("Silence detected, stopping")
                        self._is_recording = False
                
                frame_count += 1
                if frame_count >= max_frames:
                    logger.debug("Max duration reached")
                    self._is_recording = False
            
            # Start recording
            with sd.InputStream(
                device=self.device,
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.frame_size,
                dtype=np.float32,
                callback=audio_callback
            ):
                while self._is_recording:
                    sd.sleep(100)
            
            if on_speech_end:
                on_speech_end()
            
            # Convert to WAV
            if self._audio_buffer:
                return self._create_wav(self._audio_buffer)
            else:
                logger.warning("No audio captured")
                return None
                
        except Exception as e:
            logger.error(f"Recording error: {e}")
            return None
        finally:
            self._is_recording = False
    
    def stop(self) -> None:
        """Stop the current recording."""
        self._is_recording = False
        logger.debug("Recording stopped by request")
    
    def _create_wav(self, audio_chunks: List[bytes]) -> bytes:
        """Convert audio chunks to WAV format."""
        audio_data = b''.join(audio_chunks)
        
        # Create WAV in memory
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data)
        
        buffer.seek(0)
        return buffer.read()
    
    def save_wav(self, audio_data: bytes, path: str) -> None:
        """Save audio data to a WAV file."""
        with open(path, 'wb') as f:
            f.write(audio_data)
        logger.debug(f"Audio saved to {path}")
    
    def test_microphone(self, duration: float = 3.0) -> Tuple[bool, str]:
        """
        Test microphone by recording briefly.
        
        Returns:
            Tuple of (success, message)
        """
        logger.info(f"Testing microphone for {duration} seconds...")
        
        try:
            # Record for test duration
            recorded = []
            
            def callback(indata, frames, time_info, status):
                recorded.append(indata.copy())
            
            with sd.InputStream(
                device=self.device,
                channels=self.channels,
                samplerate=self.sample_rate,
                dtype=np.float32,
                callback=callback
            ):
                sd.sleep(int(duration * 1000))
            
            if recorded:
                # Calculate average level
                all_audio = np.concatenate(recorded)
                level = np.abs(all_audio).mean()
                
                if level < 0.001:
                    return False, "⚠️ Microphone detected but very quiet. Check input volume."
                else:
                    return True, f"✅ Microphone working! Average level: {level:.4f}"
            else:
                return False, "❌ No audio captured"
                
        except Exception as e:
            return False, f"❌ Microphone error: {e}"
