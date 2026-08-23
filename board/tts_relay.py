#!/usr/bin/env python3
"""
HapticTalk - TTS relay (pre-rendered clips)

Runs ON THE HOST, not in the App Lab container.

Plays pre-rendered neural TTS clips for known sentences, and falls back to
espeak-ng for anything not in the manifest. The container has no sudo and
cannot reach lightdm's PipeWire session, which is where the board's working
audio lives - hence this relay.

Setup on the board:
    sudo apt install -y mpg123
    # copy audio_clips/ from your laptop to ~/audio_clips/

Run:
    python3 ~/tts_relay.py

Background:
    nohup python3 ~/tts_relay.py > /tmp/tts_relay.log 2>&1 &
"""

import json
import os
import socket
import subprocess
import threading

HOST = "0.0.0.0"
PORT = 5006

CLIPS_DIR = os.path.expanduser("~/audio_clips")
MANIFEST = os.path.join(CLIPS_DIR, "manifest.json")

# Reach into lightdm's session - that is where the audio stack lives.
AS_LIGHTDM = ["sudo", "-n", "-u", "lightdm",
              "env", "XDG_RUNTIME_DIR=/run/user/103"]

clips = {}


def load_manifest():
    global clips
    try:
        with open(MANIFEST) as f:
            clips = json.load(f)
        print(f"[relay] loaded {len(clips)} clips from {CLIPS_DIR}", flush=True)
    except Exception as e:
        print(f"[relay] no manifest ({e}) - espeak fallback only", flush=True)
        clips = {}


def play_clip(fname):
    path = os.path.join(CLIPS_DIR, fname)
    if not os.path.exists(path):
        return False
    try:
        r = subprocess.run(
            AS_LIGHTDM + ["mpg123", "-q", path],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode != 0:
            print(f"[relay] mpg123 rc={r.returncode}: {r.stderr.strip()[:200]}", flush=True)
            return False
        return True
    except FileNotFoundError:
        print("[relay] mpg123 not installed - run: sudo apt install -y mpg123", flush=True)
        return False
    except Exception as e:
        print(f"[relay] play error: {e}", flush=True)
        return False


def espeak(text):
    try:
        subprocess.run(
            AS_LIGHTDM + ["espeak-ng", "-s", "150", "-v", "en", text],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as e:
        print(f"[relay] espeak error: {e}", flush=True)


def speak(text):
    fname = clips.get(text)
    if fname and play_clip(fname):
        print(f"[relay] clip: {text}", flush=True)
        return

    # Not pre-rendered (or playback failed) - fall back so nothing is silent.
    print(f"[relay] espeak fallback: {text}", flush=True)
    espeak(text)


def handle(conn, addr):
    buf = ""
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data.decode("utf-8", errors="ignore")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if line:
                    speak(line)
    except Exception as e:
        print(f"[relay] connection error: {e}", flush=True)
    finally:
        conn.close()


def main():
    load_manifest()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(5)
    print(f"[relay] listening on {HOST}:{PORT}", flush=True)

    # Prove audio works now rather than discovering it mid-demo.
    speak("HapticTalk ready")

    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
