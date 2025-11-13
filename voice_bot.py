import os
from dotenv import load_dotenv
import pyttsx3
import speech_recognition as sr
from openai import OpenAI

# Load API key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize speech recognizer AND TTS engine ONCE (outside loop)
recognizer = sr.Recognizer()

# Adjust recognizer settings for better performance
recognizer.pause_threshold = 0.8
recognizer.energy_threshold = 300

# Conversation memory
conversation_history = [
    {
        "role": "system",
        "content": (
            "You are a friendly voice assistant. "
            "Answer in the same language the user speaks. "
            "Understand French and English."
        )
    }
]

# Calibrate for ambient noise once at startup
print("Calibrating microphone... Please wait.")
with sr.Microphone() as source:
    recognizer.adjust_for_ambient_noise(source, duration=2)

print("\n✅ Voice bot is running! Say 'exit', 'quit', or 'stop' to end.\n")

while True:
    # 1️⃣ Record audio
    with sr.Microphone() as source:
        print("🎤 Listening...")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            print("⏱️ No speech detected. Try again.")
            continue

    # 2️⃣ Convert speech → text (try French first, then English)
    user_text = ""
    for lang in ["fr-FR", "en-US"]:
        try:
            user_text = recognizer.recognize_google(audio, language=lang)
            lang_name = "French" if lang == "fr-FR" else "English"
            print(f"[Detected: {lang_name}]")
            break
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            print(f"❌ Google Speech API error: {e}")
            break

    if not user_text:
        print("❌ Sorry, could not understand. Please try again.")
        continue

    print(f"💬 You said: {user_text}")

    # Exit condition
    if user_text.lower() in ["exit", "quit", "stop", "arrête", "arrêter"]:
        print("👋 Goodbye!")
        break

    # Add user message to conversation memory
    conversation_history.append({"role": "user", "content": user_text})

    # 3️⃣ Send conversation → GPT
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history
        )
        bot_reply = response.choices[0].message.content
        print(f"🤖 GPT: {bot_reply}\n")

        # Add assistant reply to conversation memory
        conversation_history.append({"role": "assistant", "content": bot_reply})

        # 4️⃣ Convert GPT reply → speech
        try:
            engine = pyttsx3.init()
            engine.say(bot_reply)
            engine.runAndWait()
            engine.stop()
            # Force cleanup
            del engine
        except Exception as e:
            print(f"⚠️ TTS Error: {e}")

    except Exception as e:
        print(f"❌ Error communicating with OpenAI: {e}")
        continue