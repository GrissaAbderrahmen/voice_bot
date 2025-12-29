"""
Nova Voice Assistant - Main Orchestrator.
Connects all components and runs the main interaction loop.
"""

import asyncio
import sys
import signal
from typing import Optional
from pathlib import Path

from .core.config import Config
from .core.logger import setup_logger, get_logger
from .audio.recorder import AudioRecorder
from .audio.stt import SpeechToText
from .audio.tts import TextToSpeech
from .audio.wake_word import WakeWordDetector, PushToTalk
from .ai.llm import LLMClient
from .ai.conversation import ConversationManager


class VoiceAssistant:
    """
    Main voice assistant orchestrator.
    Manages the full voice interaction loop.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the voice assistant."""
        self.config = config or Config()
        
        # Setup logging
        self.logger = setup_logger(
            "nova",
            level=self.config.log_level,
            log_file=self.config.log_file,
            console=True
        )
        
        self.logger.info(f"🚀 Initializing {self.config.assistant_name}...")
        
        # Initialize components
        self._init_audio()
        self._init_ai()
        
        # State
        self._running = False
        self._listening = False
        
        self.logger.info(f"✅ {self.config.assistant_name} is ready!")
    
    def _init_audio(self) -> None:
        """Initialize audio components."""
        # Recorder
        self.recorder = AudioRecorder(
            sample_rate=self.config.sample_rate,
            silence_duration=self.config.silence_duration
        )
        
        # Speech-to-text
        self.stt = SpeechToText(
            model=self.config.whisper_model,
            device=self.config.whisper_device,
            languages=self.config.languages
        )
        
        # Text-to-speech
        self.tts = TextToSpeech(
            voice_en=self.config.tts_voice_en,
            voice_fr=self.config.tts_voice_fr,
            rate=self.config.tts_rate
        )
        
        # Wake word (optional)
        porcupine_key = self.config.get("porcupine", "access_key")
        if porcupine_key:
            self.wake_word = WakeWordDetector(
                access_key=porcupine_key,
                keyword="computer",  # Built-in closest to "hey nova"
                sensitivity=0.5
            )
        else:
            self.wake_word = None
            self.push_to_talk = PushToTalk()
    
    def _init_ai(self) -> None:
        """Initialize AI components."""
        # LLM client
        self.llm = LLMClient(
            model=self.config.openai_model,
            max_tokens=self.config.get("openai", "max_tokens", default=500),
            temperature=self.config.get("openai", "temperature", default=0.7)
        )
        
        # Conversation manager
        self.conversation = ConversationManager(
            system_prompt=self.config.system_prompt,
            max_history=self.config.max_history,
            persist=self.config.persist_conversations
        )
    
    async def _process_speech(self) -> None:
        """Record, transcribe, and respond to user speech."""
        self._listening = True
        
        # Show we're listening
        print("\n🎤 Listening...")
        
        # Record audio
        audio = self.recorder.record(
            max_duration=15.0,
            on_speech_start=lambda: print("💬 Speech detected..."),
            on_speech_end=lambda: print("⏳ Processing...")
        )
        
        self._listening = False
        
        if not audio:
            self.logger.warning("No audio captured")
            return
        
        # Transcribe
        text, lang = self.stt.transcribe(audio)
        
        if not text or len(text.strip()) < 2:
            print("❌ Could not understand, please try again.")
            return
        
        print(f"📝 You: {text}")
        
        # Check for exit commands
        exit_commands = ["exit", "quit", "stop", "goodbye", "bye", "arrête", "au revoir"]
        if text.lower().strip() in exit_commands:
            await self._say_goodbye(lang)
            self.stop()
            return
        
        # Check for stop speaking command
        if text.lower().strip() in ["stop", "arrête", "tais-toi", "shut up"]:
            self.tts.stop()
            return
        
        # Add to conversation
        self.conversation.add_user_message(text)
        
        # Get LLM response
        print("🤔 Thinking...")
        
        response = ""
        async for chunk in self.llm.stream_chat(self.conversation.messages_for_llm):
            response += chunk
            print(chunk, end="", flush=True)
        
        print()  # New line after response
        
        # Add response to conversation
        self.conversation.add_assistant_message(response)
        
        # Speak response
        await self.tts.speak(response, lang=lang, wait=True)
    
    async def _say_goodbye(self, lang: str = "en") -> None:
        """Say goodbye before exiting."""
        if lang.startswith("fr"):
            await self.tts.speak("Au revoir! À bientôt!", lang="fr")
        else:
            await self.tts.speak("Goodbye! Have a great day!", lang="en")
    
    async def _on_wake_word(self) -> None:
        """Called when wake word is detected."""
        self.logger.info("Wake word detected!")
        await self._process_speech()
    
    def _on_interrupt(self) -> None:
        """Handle keyboard interrupt."""
        self.logger.info("Interrupt received, shutting down...")
        self.stop()
    
    async def run_async(self) -> None:
        """Run the assistant (async version)."""
        self._running = True
        
        print(f"\n{'='*50}")
        print(f"  🎙️  {self.config.assistant_name} Voice Assistant")
        print(f"{'='*50}")
        
        if self.wake_word and self.wake_word.is_available:
            print(f"  Say '{self.config.wake_word}' to start")
        else:
            print("  Press Enter to speak (push-to-talk mode)")
        
        print("  Say 'exit' or 'quit' to stop")
        print(f"{'='*50}\n")
        
        # Greet user
        await self.tts.speak(f"Hello! I'm {self.config.assistant_name}. How can I help you?", lang="en")
        
        try:
            if self.wake_word and self.wake_word.is_available:
                # Wake word mode
                self.wake_word.start(lambda: asyncio.create_task(self._on_wake_word()))
                
                while self._running:
                    await asyncio.sleep(0.1)
            else:
                # Push-to-talk mode
                while self._running:
                    try:
                        await asyncio.get_event_loop().run_in_executor(None, input)
                        if self._running:
                            await self._process_speech()
                    except EOFError:
                        break
                        
        except KeyboardInterrupt:
            self._on_interrupt()
        finally:
            self.cleanup()
    
    def run(self) -> None:
        """Run the assistant (sync entry point)."""
        try:
            asyncio.run(self.run_async())
        except KeyboardInterrupt:
            self._on_interrupt()
    
    def stop(self) -> None:
        """Stop the assistant."""
        self._running = False
        self.tts.stop()
        
        if self.wake_word:
            self.wake_word.stop()
    
    def cleanup(self) -> None:
        """Clean up resources."""
        self.stop()
        
        if self.wake_word:
            self.wake_word.cleanup()
        
        self.logger.info("Assistant shut down")
    
    def test_microphone(self) -> None:
        """Test the microphone."""
        success, message = self.recorder.test_microphone()
        print(message)
        return success
    
    def list_devices(self) -> None:
        """List available audio devices."""
        devices = AudioRecorder.list_devices()
        
        print("\n📱 Available Audio Input Devices:")
        print("-" * 40)
        
        for device in devices:
            print(f"  [{device['index']}] {device['name']}")
            print(f"      Channels: {device['channels']}, Sample Rate: {device['sample_rate']}")
        
        print()
    
    async def list_voices(self) -> None:
        """List available TTS voices."""
        print("\n🗣️ Available TTS Voices:")
        print("-" * 40)
        
        voices = await TextToSpeech.list_voices()
        
        current_lang = ""
        for voice in voices[:30]:  # Limit to 30 voices
            lang = voice['locale'].split('-')[0]
            if lang != current_lang:
                current_lang = lang
                print(f"\n  {voice['locale'][:2].upper()}:")
            
            gender_icon = "♀️" if voice['gender'] == "Female" else "♂️"
            print(f"    {gender_icon} {voice['name']}")
        
        print("\n  ... and more. Use specific language code for full list.")
        print()


def create_assistant() -> VoiceAssistant:
    """Factory function to create a configured assistant."""
    return VoiceAssistant()
