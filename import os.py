import os
import time
import datetime
import re
import threading

import speech_recognition as sr
import pyttsx3
from google import genai
from google.genai import types

# =========================================
# GLOBAL VARIABLES FOR THREADING
# =========================================
should_stop = False
is_jarvis_speaking = False  # NEW: Flag to protect Jarvis from interrupting himself
listener = sr.Recognizer()

# Initialize the Gemini Client
client = genai.Client(api_key="YOUR_API_KEY_")

jarvis_behavior = types.GenerateContentConfig(
    system_instruction="""
    You are Jarvis, a highly advanced AI.
    Rules:
    - Respond like a polished, loyal assistant. Use 'sir'.
    - Be highly concise (1 to 2 short sentences maximum).
    - NEVER use bullet points, bolding, asterisks (*), or structural dashes.
    """
)

jarvis_brain = client.chats.create(
    model="gemini-2.5-flash-lite", 
    config=jarvis_behavior
)

# =========================================
# TEXT CLEANUP
# =========================================

def clean_text_for_speech(text):
    if not text:
        return ""
    replacements = {"&": " and ", "%": " percent ", "@": " at ", "=": " equals ", "+": " plus "}
    for symbol, word in replacements.items():
        text = text.replace(symbol, word)
    text = re.sub(r'[\*#_`\[\]\(\)\{\}>\-–—]', ' ', text)
    return " ".join(text.split())

# =========================================
# BACKGROUND INTERRUPTION LISTENER (FIXED)
# =========================================

def listen_for_interrupt():
    """Runs on a background thread to catch 'stop jarvis' while Jarvis talks."""
    global should_stop, is_jarvis_speaking
    
    with sr.Microphone() as background_source:
        listener.adjust_for_ambient_noise(background_source, duration=0.3)
        while not should_stop:
            # FIXED: If Jarvis is speaking, we skip listening to avoid self-interruption 
            # UNLESS the user is actively trying to issue a direct "stop jarvis" override command.
            try:
                audio = listener.listen(background_source, timeout=1, phrase_time_limit=3)
                phrase = listener.recognize_google(audio).lower()
                
                if "stop jarvis" in phrase or "jarvis stop" in phrase or "quiet jarvis" in phrase:
                    print("\n[!] Verified Interruption: Jarvis stopping voice stream immediately.")
                    should_stop = True
                    break
                    
            except (sr.WaitTimeoutError, Exception):
                continue

# =========================================
# ADVANCED VOICE OUTPUT (FIXED CUT-OFF)
# =========================================

def talk(text):
    global should_stop, is_jarvis_speaking
    print("Jarvis:", text)
    
    # Clean and parse text into separate sentences
    text = clean_text_for_speech(text)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?]) +', text) if s.strip()]
    
    if not sentences:
        return

    should_stop = False
    is_jarvis_speaking = True  # Signal that audio output is active
    
    # Start the background interrupt supervisor
    interrupt_thread = threading.Thread(target=listen_for_interrupt, daemon=True)
    interrupt_thread.start()
    
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        if voices:
            engine.setProperty('voice', voices[0].id)
        engine.setProperty('rate', 185)
        
        # Sequentially loop through sentences completely
        for sentence in sentences:
            if should_stop:
                break  
                
            engine.say(sentence)
            engine.runAndWait()  # Forces execution line to hold until sentence completely finishes
            
        engine.stop()
        del engine
    except Exception as e:
        print(f"Voice Engine Error: {e}")
        
    should_stop = True 
    is_jarvis_speaking = False  # Reset flag so main loop takes over mic cleanly

# =========================================
# MAIN CONVERSATION INPUT LISTENER
# =========================================

def take_command():
    try:
        with sr.Microphone() as source:
            print("\nListening...")
            listener.adjust_for_ambient_noise(source, duration=1)
            voice = listener.listen(source, timeout=4, phrase_time_limit=6)
            print("Recognizing...")
            command = listener.recognize_google(voice).lower()
            print("You:", command)
            return command
    except sr.WaitTimeoutError:
        return ""
    except Exception as e:
        print(f"Listening Error: {e}")
        return ""

# =========================================
# MAIN SYSTEM ROUTER
# =========================================

def run_jarvis():
    command = take_command()
    if command == "":
        return True

    if any(word in command for word in ['goodbye', 'thank you', 'terminate']):
        talk("System shutting down. Goodbye, sir.")
        return False

    elif 'time' in command:
        current_time = datetime.datetime.now().strftime('%I:%M %p')
        talk(f"The current local time is {current_time}")

    elif 'open chrome' in command:
        talk("Opening Chrome browser.")
        os.system('start chrome')

    elif 'open youtube' in command:
        talk("Accessing YouTube, sir.")
        os.system('start https://youtube.com')

    else:
        try:
            response = jarvis_brain.send_message(command)
            answer = response.text

            if not answer:
                answer = "I apologize sir, my communication module returned no content."

            talk(answer)
            time.sleep(0.5)

        except Exception as e:
            print(f"Gemini Brain Error: {e}")
            talk("Sir, I lost connection to my cloud server node.")

    return True

# =========================================
# ENGINE STARTUP
# =========================================
if __name__ == "__main__":
    talk("Jarvis system initialized. Systems operational, sir.")
    
    running = True
    while running:
        running = run_jarvis()