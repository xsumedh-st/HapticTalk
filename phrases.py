"""
HapticTalk - phrase tables (single source of truth)

Pure data: no hardware init, no loops, no network, no imports beyond the
standard library. Both main.py (on the board) and generate_audio.py (on the
laptop) import from here so their phrase text cannot drift apart again.

Canonical text below matches audio_clips/manifest.json (the already-rendered
clips), not main.py's current hardcoded INTRO_PATTERNS - regenerating audio
is more expensive than editing a dict. As of this writing main.py's copy of
INTRO_PATTERNS has NOT been updated to match and needs a manual edit on the
board; see the two entries below.
"""

STARTUP_PHRASE = "HapticTalk ready"

INTRO_PATTERNS = {
    ("GOODMORNING", "I", "NAME"):  "Good morning, my name is Sumedh.",
    ("TODAY", "I", "DEMONSTRATE"): "Today I will be demonstrating",
    ("AI", "COMMUNICATION"):       "HapticTalk, an AI-powered communication glove",
    ("HELP", "DEAF"):              "that helps the deaf speak,",
    ("HELP", "BLIND"):             "and lets a deaf-blind person feel the reply on their fingertips.",
}

GENERAL_PATTERNS = {
    ("I", "PAIN", "DOCTOR"):  "I am in pain, please call a doctor.",
    ("PLEASE", "DOCTOR"):     "Please call a doctor immediately.",
    ("DOCTOR", "HOSPITAL"):   "Please take me to the hospital.",
    ("I", "MEDICINE"):        "I need my medicine urgently.",
    ("I", "PAIN"):            "I am in pain.",
    ("I", "HELP"):            "I need help.",
    ("I", "THIRSTY"):         "I am thirsty, I need water.",
    ("I", "WATER"):           "I need water.",
    ("I", "FOOD"):            "I am hungry, I need food.",
    ("PLEASE", "UNDERSTAND"): "Please help me, I don't understand.",
    ("SORRY", "UNDERSTAND"):  "I am sorry, I don't understand.",
    ("I", "UNDERSTAND"):      "I understand, thank you.",
    ("THANKYOU", "HELP"):     "Thank you for your help.",
    ("GOODMORNING", "HELP"):  "Good morning, can you please help me?",
    ("I", "NAME"):            "My name is Sumedh.",
    ("I", "DEAF"):            "I am deaf.",
}

SINGLE_WORD_OK = {
    "YES": "Yes.", "NO": "No.", "HELP": "Help!", "PAIN": "Pain.",
    "WATER": "Water.", "THANKYOU": "Thank you.", "SORRY": "Sorry.",
    "PLEASE": "Please.", "GOODMORNING": "Good morning.",
}


def all_sentences():
    """Every sentence this system can speak, across every table."""
    values = [STARTUP_PHRASE]
    values += list(INTRO_PATTERNS.values())
    values += list(GENERAL_PATTERNS.values())
    values += list(SINGLE_WORD_OK.values())
    return values
