# Voice Assistant - Nova

A professional, modular voice assistant with wake word detection, multi-language support, and a web dashboard.

## Features

- 🎤 **Wake Word Detection** - "Hey Nova" activation
- 🗣️ **Natural Speech** - Microsoft Edge neural voices (free)
- 👂 **Accurate STT** - Local Whisper (free, offline)
- 🧠 **Smart Responses** - GPT-4o-mini powered
- 🌍 **Multi-language** - English & French
- 💾 **Memory** - Remembers conversation context
- 🌐 **Web Dashboard** - Configure and monitor

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the assistant
python main.py

# Or with debug mode
python main.py --debug
```

## Commands

```bash
python main.py              # Start assistant
python main.py --setup      # Interactive setup
python main.py --test-mic   # Test microphone
python main.py --list-voices # List TTS voices
python main.py --web        # Start web dashboard only
```

## Configuration

Edit `config.yaml` to customize:
- Wake word
- TTS voice
- Whisper model size
- System prompt
- And more...

## Testing the Assistant

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Test Your Microphone
```bash
python main.py --test-mic
```
You should see "✅ Microphone working!" with an audio level.

### Step 3: List Audio Devices (Optional)
```bash
python main.py --list-devices
```
If your mic isn't detected, check the device index here.

### Step 4: Test TTS Voices
```bash
python main.py --list-voices
```
Shows available English and French voices.

### Step 5: Run the Assistant
```bash
python main.py
```

**What happens:**
1. First run downloads Whisper model (~150MB) — wait for it
2. Nova greets you: "Hello! I'm Nova. How can I help you?"
3. Press **Enter** to speak (push-to-talk mode)
4. Speak in English or French
5. Nova responds with voice
6. Say "exit" or "quit" to stop

### Step 6: Try the Web Dashboard
```bash
python main.py --web
```
Open http://127.0.0.1:5000 in your browser.

### Troubleshooting

| Problem | Solution |
|---------|----------|
| "No microphone detected" | Check Windows sound settings, allow mic access |
| "OpenAI API key not found" | Add `OPENAI_API_KEY=sk-xxx` to `.env` file |
| Whisper download stuck | Check internet connection, try again |
| No sound output | Check Windows audio output, pygame needs speakers |
| Edge-TTS error | Run `pip install edge-tts --upgrade` |

## Requirements

- Python 3.10+
- Microphone
- OpenAI API key (for GPT)
