"""
Nova Voice Assistant - Web Dashboard
Flask-based web interface for configuration and monitoring.
"""

import asyncio
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from pathlib import Path
import json

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.config import Config
from src.core.logger import get_logger
from src.ai.conversation import ConversationManager
from src.audio.tts import TextToSpeech

logger = get_logger("nova.web")

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'nova-voice-assistant-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global state
config = Config()


def create_app() -> Flask:
    """Create and configure the Flask app."""
    return app


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html', config=config.to_dict())


@app.route('/api/config')
def get_config():
    """Get current configuration."""
    return jsonify(config.to_dict())


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration."""
    data = request.json
    # TODO: Implement config update
    return jsonify({"status": "ok"})


@app.route('/api/conversations')
def list_conversations():
    """List all saved conversations."""
    sessions = ConversationManager.list_sessions()
    return jsonify(sessions)


@app.route('/api/conversations/<session_id>')
def get_conversation(session_id):
    """Get a specific conversation."""
    sessions = ConversationManager.list_sessions()
    
    for session in sessions:
        if session['session_id'] == session_id:
            with open(session['path'], 'r') as f:
                return jsonify(json.load(f))
    
    return jsonify({"error": "Session not found"}), 404


@app.route('/api/voices')
def list_voices():
    """List available TTS voices."""
    try:
        voices = asyncio.run(TextToSpeech.list_voices())
        return jsonify(voices)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/voices/preview', methods=['POST'])
def preview_voice():
    """Preview a TTS voice."""
    data = request.json
    voice = data.get('voice', 'en-US-AriaNeural')
    text = data.get('text', 'Hello, this is a voice preview.')
    
    try:
        tts = TextToSpeech(voice_en=voice)
        audio = asyncio.run(tts.synthesize(text, voice))
        
        # Return as base64
        import base64
        audio_b64 = base64.b64encode(audio).decode('utf-8')
        return jsonify({"audio": audio_b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/status')
def get_status():
    """Get assistant status."""
    return jsonify({
        "status": "ready",
        "name": config.assistant_name,
        "wake_word": config.wake_word,
        "model": config.openai_model
    })


# SocketIO events for real-time updates
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    logger.info("Web client connected")
    emit('status', {"connected": True})


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    logger.info("Web client disconnected")


@socketio.on('start_listening')
def handle_start_listening():
    """Start listening for voice input."""
    emit('status', {"listening": True})
    # TODO: Integrate with actual assistant


@socketio.on('stop_listening')
def handle_stop_listening():
    """Stop listening."""
    emit('status', {"listening": False})


# Run standalone
if __name__ == '__main__':
    app.run(
        host=config.web_host,
        port=config.web_port,
        debug=True
    )
