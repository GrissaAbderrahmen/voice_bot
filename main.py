#!/usr/bin/env python3
"""
Nova Voice Assistant - Entry Point

Usage:
    python main.py              # Start the assistant
    python main.py --debug      # Start with debug logging
    python main.py --test-mic   # Test microphone
    python main.py --list-devices # List audio devices
    python main.py --list-voices  # List TTS voices
    python main.py --web        # Start web dashboard only
    python main.py --setup      # Interactive setup
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.assistant import VoiceAssistant
from src.core.config import Config
from src.core.logger import setup_logger


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Nova Voice Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Enable debug logging"
    )
    
    parser.add_argument(
        "--test-mic",
        action="store_true",
        help="Test microphone"
    )
    
    parser.add_argument(
        "--list-devices",
        action="store_true", 
        help="List available audio devices"
    )
    
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="List available TTS voices"
    )
    
    parser.add_argument(
        "--web",
        action="store_true",
        help="Start web dashboard only"
    )
    
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run interactive setup"
    )
    
    parser.add_argument(
        "--continue",
        dest="continue_session",
        action="store_true",
        help="Continue last conversation"
    )
    
    args = parser.parse_args()
    
    # Debug logging
    if args.debug:
        import os
        os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Handle different modes
    if args.setup:
        run_setup()
        return
    
    if args.list_devices:
        assistant = VoiceAssistant()
        assistant.list_devices()
        return
    
    if args.list_voices:
        from src.audio.tts import TextToSpeech
        asyncio.run(show_voices())
        return
    
    if args.test_mic:
        assistant = VoiceAssistant()
        assistant.test_microphone()
        return
    
    if args.web:
        run_web_dashboard()
        return
    
    # Normal run
    try:
        assistant = VoiceAssistant()
        assistant.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.debug:
            raise
        sys.exit(1)


async def show_voices():
    """Show available TTS voices."""
    from src.audio.tts import TextToSpeech
    
    print("\n🗣️ Available TTS Voices:")
    print("-" * 50)
    
    for lang_code in ["en", "fr"]:
        voices = await TextToSpeech.list_voices(lang_code)
        
        print(f"\n  {lang_code.upper()}:")
        for voice in voices[:10]:
            gender_icon = "♀️" if voice['gender'] == "Female" else "♂️"
            print(f"    {gender_icon} {voice['name']}")
    
    print()


def run_setup():
    """Interactive setup wizard."""
    from pathlib import Path
    import os
    
    print("\n🔧 Nova Voice Assistant Setup")
    print("=" * 40)
    
    # Check for .env
    env_path = Path(__file__).parent / ".env"
    
    if not env_path.exists():
        print("\n1. OpenAI API Key")
        print("   Get your key at: https://platform.openai.com/api-keys")
        api_key = input("   Enter your OpenAI API key: ").strip()
        
        if api_key:
            with open(env_path, 'w') as f:
                f.write(f"OPENAI_API_KEY={api_key}\n")
            print("   ✅ API key saved to .env")
        else:
            print("   ⚠️ Skipped. You'll need to set OPENAI_API_KEY manually.")
    else:
        print("\n1. OpenAI API Key: ✅ Already configured")
    
    # Test microphone
    print("\n2. Testing Microphone...")
    try:
        from src.audio.recorder import AudioRecorder
        recorder = AudioRecorder()
        success, message = recorder.test_microphone(duration=2.0)
        print(f"   {message}")
    except Exception as e:
        print(f"   ⚠️ Microphone test failed: {e}")
    
    # Porcupine key
    print("\n3. Wake Word Detection (Optional)")
    print("   Get a FREE key at: https://console.picovoice.ai/")
    porcupine_key = input("   Enter Porcupine access key (or press Enter to skip): ").strip()
    
    if porcupine_key:
        with open(env_path, 'a') as f:
            f.write(f"PORCUPINE_ACCESS_KEY={porcupine_key}\n")
        print("   ✅ Porcupine key saved")
    else:
        print("   ℹ️ Skipped. Using push-to-talk mode.")
    
    print("\n✅ Setup complete! Run 'python main.py' to start.")
    print()


def run_web_dashboard():
    """Start the web dashboard."""
    try:
        from src.web.app import create_app
        
        app = create_app()
        config = Config()
        
        print(f"\n🌐 Starting web dashboard at http://{config.web_host}:{config.web_port}")
        app.run(
            host=config.web_host,
            port=config.web_port,
            debug=config.get("web", "debug", default=False)
        )
    except ImportError:
        print("❌ Web dashboard not available. Install Flask first.")
        print("   pip install flask flask-socketio")


if __name__ == "__main__":
    main()
