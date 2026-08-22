"""
HapticTalk - push-to-talk speech -> haptic.

Runs on the LAPTOP. Press ENTER, speak one word, and the glove buzzes the
matching pattern. This is the reply direction: a hearing person speaks, the
deaf-blind user feels it on their fingertips.

It sends to mediapipe_bridge.py over localhost, and the bridge forwards the
word to the board down the socket it already has open. That avoids opening a
second port on the board (app.yaml is read-only) and means no firewall or
network config is involved at all.

Push-to-talk rather than always listening is deliberate - the JBL speaker is in
the same room, and continuous listening would transcribe the system's own
speech and buzz the glove at itself.

Setup:
    python -m pip install SpeechRecognition pyaudio

Run (mediapipe_bridge.py must already be running):
    python listen.py

Needs internet - transcription uses Google's free Web Speech endpoint.
"""

import os
import socket
import sys

try:
    import speech_recognition as sr
except ImportError:
    sys.exit("SpeechRecognition not installed. Run:\n"
             "    python -m pip install SpeechRecognition pyaudio")

# The bridge listens here, on this machine only.
HOST = os.environ.get("HAPTIC_RELAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("HAPTIC_RELAY_PORT", "5099"))

# Spoken word -> glove label. Several spellings map to the same buzz so people
# can talk normally instead of reciting the label list.
ALIASES = {
    "pain": "PAIN", "hurt": "PAIN", "hurts": "PAIN", "hurting": "PAIN",
    "help": "HELP",
    "doctor": "DOCTOR",
    "hospital": "HOSPITAL",
    "medicine": "MEDICINE", "medicines": "MEDICINE", "medication": "MEDICINE",
    "water": "WATER",
    "food": "FOOD", "eat": "FOOD", "hungry": "FOOD",
    "thirsty": "THIRSTY", "thirst": "THIRSTY",
    "yes": "YES", "yeah": "YES", "yep": "YES", "okay": "YES", "ok": "YES",
    "no": "NO", "nope": "NO",
    "please": "PLEASE",
    "thanks": "THANKYOU", "thank": "THANKYOU",
    "sorry": "SORRY",
    "understand": "UNDERSTAND", "understood": "UNDERSTAND",
    "name": "NAME",
    "deaf": "DEAF",
    "blind": "BLIND",
    "today": "TODAY",
    "morning": "GOODMORNING",
    "demonstrate": "DEMONSTRATE",
    "communication": "COMMUNICATION",
    "ai": "AI",
    "i": "I",
}


def send(word):
    with socket.create_connection((HOST, PORT), timeout=3) as s:
        s.sendall((word + "\n").encode("utf-8"))


def match(text):
    """First recognised word wins."""
    for token in text.lower().split():
        token = token.strip(".,!?;:")
        if token in ALIASES:
            return ALIASES[token]
    return None


def main():
    recognizer = sr.Recognizer()
    try:
        mic = sr.Microphone()
    except Exception as e:
        sys.exit(f"No microphone available: {e}")

    with mic as source:
        print("calibrating for background noise (stay quiet)...")
        recognizer.adjust_for_ambient_noise(source, duration=1)

    print(f"\nready. sending to bridge at {HOST}:{PORT}")
    print("press ENTER, then say one word. ctrl-c to quit.\n")

    while True:
        try:
            input("[ENTER to listen] ")
        except (KeyboardInterrupt, EOFError):
            print("\nbye")
            return

        with mic as source:
            print("  listening...")
            try:
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=3)
            except sr.WaitTimeoutError:
                print("  heard nothing\n")
                continue

        try:
            text = recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            print("  couldn't make that out\n")
            continue
        except sr.RequestError as e:
            print(f"  speech service unreachable: {e}\n")
            continue

        print(f"  heard: {text!r}")

        word = match(text)
        if not word:
            print("  no word I recognise in that\n")
            continue

        try:
            send(word)
            print(f"  -> glove: {word}\n")
        except Exception as e:
            print(f"  send failed: {e}")
            print("  is mediapipe_bridge.py running?\n")


if __name__ == "__main__":
    main()