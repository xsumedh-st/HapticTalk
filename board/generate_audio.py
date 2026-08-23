#!/usr/bin/env python3
"""
HapticTalk - generate speech clips

Runs on your LAPTOP, not the board.

Renders every sentence HapticTalk can say into an audio file using Microsoft
Edge's neural voices. Free, no API key, and far more natural than espeak.

Setup:
    pip install edge-tts

Run:
    python generate_audio.py

Then copy the whole folder to the board:
    scp -r audio_clips arduino@10.171.220.95:~/

Listen to every clip before demo day. Anything that sounds wrong, fix the
text (spelling it phonetically usually works) and re-run.
"""

import asyncio
import hashlib
import json
import os

import edge_tts

# Voices worth trying - run with a different one if you dislike this:
#   en-US-AriaNeural      warm, natural (default)
#   en-US-JennyNeural     friendly, clear
#   en-GB-SoniaNeural     British
#   en-IN-NeerjaNeural    Indian English
#   en-IN-PrabhatNeural   Indian English, male
VOICE = "en-IN-NeerjaNeural"

RATE = "-5%"      # slightly slower reads more clearly on a small speaker
OUTDIR = "audio_clips"


# Every sentence the system can speak. Must match main.py.
SENTENCES = [
    # startup
    "HapticTalk ready",

    # intro
    "Good morning, my name is Sumedh.",
    "Today I will be demonstrating",
    "HapticTalk, an AI-powered communication glove",
    "that helps the deaf speak,",
    "and lets a deaf-blind person feel the reply on their fingertips.",

    # general phrases
    "I am in pain, please call a doctor.",
    "Please call a doctor immediately.",
    "Please take me to the hospital.",
    "I need my medicine urgently.",
    "I am in pain.",
    "I need help.",
    "I am thirsty, I need water.",
    "I need water.",
    "I am hungry, I need food.",
    "Please help me, I don't understand.",
    "I am sorry, I don't understand.",
    "I understand, thank you.",
    "Thank you for your help.",
    "Good morning, can you please help me?",
    "My name is Sumedh.",
    "I am deaf.",

    # single words
    "Yes.",
    "No.",
    "Help!",
    "Pain.",
    "Water.",
    "Thank you.",
    "Sorry.",
    "Please.",
    "Good morning.",
]


def key_for(text):
    """Stable filename for a sentence."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


async def render(text, path):
    comm = edge_tts.Communicate(text, VOICE, rate=RATE)
    await comm.save(path)


async def main():
    os.makedirs(OUTDIR, exist_ok=True)
    manifest = {}

    for i, text in enumerate(SENTENCES, 1):
        k = key_for(text)
        fname = f"{k}.mp3"
        path = os.path.join(OUTDIR, fname)

        print(f"[{i:2}/{len(SENTENCES)}] {text}")
        await render(text, path)
        manifest[text] = fname

    with open(os.path.join(OUTDIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nDone. {len(SENTENCES)} clips in ./{OUTDIR}/")
    print("Listen to them all before you rely on them.")
    print(f"\nCopy to the board:\n  scp -r {OUTDIR} arduino@10.171.220.95:~/")


if __name__ == "__main__":
    asyncio.run(main())
