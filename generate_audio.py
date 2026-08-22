#!/usr/bin/env python3
"""
HapticTalk - generate speech clips

Runs on your LAPTOP, not the board.

Renders every sentence HapticTalk can say into an audio file using Microsoft
Edge's neural voices. Free, no API key, and far more natural than espeak.

Sentence text comes from phrases.py, the single source of truth shared with
main.py - this script no longer keeps its own copy.

Setup:
    pip install edge-tts

Run:
    python generate_audio.py

Listen to every clip before demo day. Anything that sounds wrong, fix the
text in phrases.py (spelling it phonetically usually works) and re-run.
"""

import asyncio
import hashlib
import json
import os

import edge_tts

from phrases import all_sentences

# Voices worth trying - run with a different one if you dislike this:
#   en-US-AriaNeural      warm, natural (default)
#   en-US-JennyNeural     friendly, clear
#   en-GB-SoniaNeural     British
#   en-IN-NeerjaNeural    Indian English
#   en-IN-PrabhatNeural   Indian English, male
VOICE = "en-IN-NeerjaNeural"

RATE = "-5%"      # slightly slower reads more clearly on a small speaker
OUTDIR = "audio_clips"

SENTENCES = sorted(set(all_sentences()))


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


if __name__ == "__main__":
    asyncio.run(main())
