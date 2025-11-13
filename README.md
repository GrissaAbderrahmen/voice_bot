# Voice Bot - Phase 1

A simple voice assistant using OpenAI GPT-4o-mini.  
Speak in English or French and get voice replies.

## Features
- Speech-to-text (English & French)
- Text-to-speech responses
- Conversation memory for context

## Setup

1. Clone the repository:  
   ```bash
   git clone https://github.com/GrissaAbderrahmen/voice_bot.git
   cd voice_bot
2. Create & activate virtual environment:
  python -m venv venv
  venv\Scripts\activate   # Windows
  # OR
  source venv/bin/activate  # Mac/Linux
3. Install dependencies:
  pip install -r requirements.txt
4. Create .env file with your OpenAI API key:
  OPENAI_API_KEY=your_api_key_here
5. python voice_bot.py

Say exit, quit, or stop to end the conversation.
