
import os
import queue
import re
import subprocess
import time
import webbrowser
from datetime import datetime

import  speech_recognition as sr
from apscheduler.schedulers.background import BackgroundScheduler
from dateutil import parser as date_parser
import pyttsx3

# Initialize components
recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
recognizer.pause_threshold = 0.8
scheduler = BackgroundScheduler()
scheduler.start()
engine = pyttsx3.init()  # For text-to-speech responses

WAKE_WORD = "jarvis"  # set to "" to disable wake word for debugging
DEBUG = True

APP_ALIASES = {
    "browser": 'start "" "chrome"',
    "chrome": 'start "" "chrome"',
    "calculator": "calc",
    "notepad": "notepad",
    "youtube": "https://www.youtube.com",
}

audio_queue = queue.Queue()

def speak(text):
    """Speak the response aloud."""
    engine.say(text)
    engine.runAndWait()

def _audio_callback(_, audio):
    audio_queue.put(audio)

def start_listening():
    """Start background listening and return a stop function."""
    mic = sr.Microphone()
    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
    return recognizer.listen_in_background(mic, _audio_callback, phrase_time_limit=8)

def transcribe(audio):
    """Convert audio to text."""
    try:
        text = recognizer.recognize_google(audio)
        if DEBUG:
            print(f"You said: {text}")
        return text.lower().strip()
    except sr.UnknownValueError:
        if DEBUG:
            print("Speech was unintelligible.")
        return None
    except sr.RequestError:
        speak("Speech recognition service is unavailable.")
        if DEBUG:
            print("Speech recognition service error (check internet).")
        return None

def parse_intent(text):
    """Parse text to extract intent and entities."""
    if not text:
        return {"intent": "unknown"}

    text = text.strip().lower()

    if text in {"exit", "quit", "stop", "shutdown"}:
        return {"intent": "exit", "entity": None}

    yt_match = re.match(r"(play|open)\s+(.*)\s+on\s+youtube", text)
    if yt_match:
        return {"intent": "youtube_search", "entity": yt_match.group(2).strip()}

    if text.startswith("youtube "):
        return {"intent": "youtube_search", "entity": text.replace("youtube", "", 1).strip()}

    if text.startswith("search "):
        return {"intent": "search", "entity": text.replace("search", "", 1).strip()}

    if text.startswith("google "):
        return {"intent": "search", "entity": text.replace("google", "", 1).strip()}

    if text.startswith("open "):
        return {"intent": "open_app", "entity": text.replace("open", "", 1).strip()}

    if "reminder" in text or "remind" in text:
        try:
            dt = date_parser.parse(text, fuzzy=True)
            task = (
                text.replace("reminder", "")
                .replace("remind", "")
                .replace(str(dt), "")
                .strip()
            )
            return {"intent": "set_reminder", "entity": {"time": dt, "task": task}}
        except Exception:
            return {"intent": "unknown"}

    return {"intent": "unknown"}

def execute_action(intent_data):
    """Execute the action based on intent."""
    intent = intent_data["intent"]
    entity = intent_data["entity"]
    
    if intent == "open_app":
        app = entity.lower()
        try:
            speak(f"Opening {app}.")
            if app in APP_ALIASES:
                target = APP_ALIASES[app]
                if target.startswith("http"):
                    webbrowser.open(target)
                else:
                    subprocess.Popen(target, shell=True)
            else:
                if os.name == "nt":
                    subprocess.Popen(f'start "" "{app}"', shell=True)
                else:
                    subprocess.Popen([app])
            return f"Opened {app}."
        except Exception as e:
            speak("Failed to open the app.")
            return f"Error: {str(e)}"
    
    elif intent == "set_reminder":
        time_obj = entity["time"]
        task = entity["task"]
        try:
            if time_obj < datetime.now():
                speak("That time is in the past. Please try again.")
                return "Reminder time was in the past."
            scheduler.add_job(lambda: speak(f"Reminder: {task}"), 'date', run_date=time_obj)
            speak(f"Reminder set for {time_obj} to {task}.")
            return f"Reminder set."
        except Exception as e:
            speak("Failed to set reminder.")
            return f"Error: {str(e)}"
    
    elif intent == "search":
        query = entity
        try:
            speak(f"Searching for {query}.")
            url = f"https://www.google.com/search?q={query}"
            webbrowser.open(url)
            return f"Searched for {query}."
        except Exception as e:
            speak("Failed to search.")
            return f"Error: {str(e)}"

    elif intent == "youtube_search":
        query = entity
        try:
            speak(f"Searching YouTube for {query}.")
            url = f"https://www.youtube.com/results?search_query={query}"
            webbrowser.open(url)
            return f"Searched YouTube for {query}."
        except Exception as e:
            speak("Failed to open YouTube.")
            return f"Error: {str(e)}"

    elif intent == "exit":
        speak("Goodbye.")
        return "Exit requested."
    
    else:
        speak("I'm not sure how to handle that.")
        return "Unknown command."

def main():
    """Main loop for the assistant."""
    speak("Hello, I'm Jarvis. How can I assist you,Romaan?")
    stop_listening = start_listening()

    try:
        while True:
            try:
                audio = audio_queue.get(timeout=0.1)
            except queue.Empty:
                time.sleep(0.05)
                continue

            text = transcribe(audio)
            if not text:
                continue

            if WAKE_WORD:
                if not text.startswith(WAKE_WORD):
                    if WAKE_WORD in text:
                        text = text.split(WAKE_WORD, 1)[1].strip()
                    else:
                        if DEBUG:
                            print("Wake word not detected. Ignoring.")
                        continue
                else:
                    text = text[len(WAKE_WORD):].strip()

            if not text:
                continue

            intent_data = parse_intent(text)
            if intent_data["intent"] == "unknown":
                speak("I didn't understand. Can you clarify?")
                continue

            response = execute_action(intent_data)
            print(response)  # For debugging
            if intent_data["intent"] == "exit":
                break
    finally:
        stop_listening(wait_for_stop=False)

if __name__ == "__main__":
    main()

    
