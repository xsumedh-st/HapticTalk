"""
HapticTalk - MediaPipe landmark bridge

Runs on your LAPTOP. Captures hand landmarks from the webcam and streams them
to the board over TCP.

Host/port can be overridden without editing this file:

    $env:HAPTICTALK_HOST = "10.171.220.95"
    $env:HAPTICTALK_PORT = "5005"
    python mediapipe_bridge.py

Check reachability without starting the webcam:

    python mediapipe_bridge.py --selftest
"""

import argparse
import os
import queue
import socket
import sys
import threading
import time

import cv2

from hands_config import make_hands

UNOQ_IP = os.environ.get("HAPTICTALK_HOST", "10.171.220.95")
UNOQ_PORT = int(os.environ.get("HAPTICTALK_PORT", "5005"))

RECONNECT_BASE_DELAY = 0.5   # seconds, doubles each attempt
RECONNECT_MAX_DELAY = 10.0

HAPTIC_HOST = "127.0.0.1"
HAPTIC_PORT = 5099


def start_haptic_channel(word_queue):
    """Listen on localhost for words to relay as HAPTIC commands.

    Returns the listening socket, or None if binding failed (the bridge
    keeps running without the haptic command channel in that case).
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((HAPTIC_HOST, HAPTIC_PORT))
    except OSError as e:
        print(f"[haptic] warning: could not bind {HAPTIC_HOST}:{HAPTIC_PORT} ({e}); "
              f"haptic command channel disabled")
        server.close()
        return None
    server.listen(5)

    def handle_conn(conn):
        try:
            with conn.makefile("r") as f:
                for line in f:
                    word = line.strip()
                    if word:
                        word_queue.put(word.upper())
        except OSError:
            pass
        finally:
            conn.close()

    def accept_loop():
        while True:
            try:
                conn, _ = server.accept()
            except OSError:
                break
            threading.Thread(target=handle_conn, args=(conn,), daemon=True).start()

    threading.Thread(target=accept_loop, daemon=True).start()
    print(f"[haptic] command channel on {HAPTIC_HOST}:{HAPTIC_PORT}")
    return server


def connect(host, port, timeout=10):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
    except OSError as e:
        sock.close()
        raise ConnectionError(
            f"Could not reach {host}:{port} ({e}).\n"
            f"  - Is the board on and main.py running?\n"
            f"  - Is the IP still {host}? It can change on reboot.\n"
            f"  - Override with: $env:HAPTICTALK_HOST = \"<ip>\"\n"
            f"  - Try: python mediapipe_bridge.py --selftest"
        ) from e
    sock.settimeout(None)
    return sock


def reconnect_with_backoff(host, port):
    delay = RECONNECT_BASE_DELAY
    while True:
        print(f"[net] reconnecting to {host}:{port} ...")
        try:
            return connect(host, port)
        except ConnectionError as e:
            print(f"[net] {e}")
            print(f"[net] retrying in {delay:.1f}s")
            time.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)


def extract_landmarks(hand_landmarks):
    """Returns flat list of 63 floats: 21 points x,y,z"""
    values = []
    for lm in hand_landmarks.landmark:
        values.extend([lm.x, lm.y, lm.z])
    return values


def run_selftest(host, port):
    print(f"connecting to {host}:{port} ...")
    try:
        sock = connect(host, port)
    except ConnectionError as e:
        print(f"[net] {e}")
        return 1
    print("connected")

    packet = ",".join(["0.0000"] * 126) + "\n"
    try:
        sock.sendall(packet.encode())
        print("sent one test frame")
    except OSError as e:
        print(f"[net] send failed: {e}")
        sock.close()
        return 1

    sock.close()
    print("selftest OK")
    return 0


def main():
    print(f"connecting to {UNOQ_IP}:{UNOQ_PORT} ...")
    try:
        sock = connect(UNOQ_IP, UNOQ_PORT)
    except ConnectionError as e:
        print(f"[net] {e}")
        sys.exit(1)
    print("connected")

    sock_lock = threading.Lock()
    word_queue = queue.Queue()
    start_haptic_channel(word_queue)

    hands = make_hands()
    cap = cv2.VideoCapture(0)

    frame_count = 0

    while True:
        success, frame = cap.read()
        if not success:
            break

        frame_count += 1

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        left_data = [0.0] * 63
        right_data = [0.0] * 63

        if results.multi_hand_landmarks:
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                label = results.multi_handedness[idx].classification[0].label
                landmark_values = extract_landmarks(hand_landmarks)
                if label == "Left":
                    left_data = landmark_values
                else:
                    right_data = landmark_values

        all_values = left_data + right_data
        packet = ",".join([f"{v:.4f}" for v in all_values]) + "\n"

        if frame_count % 2 == 0:
            words = []
            while True:
                try:
                    words.append(word_queue.get_nowait())
                except queue.Empty:
                    break

            try:
                with sock_lock:
                    for word in words:
                        sock.sendall(f"HAPTIC {word}\n".encode())
                        print(f"[haptic] sent {word}")
                    sock.sendall(packet.encode())
                print(f"Left wrist X: {left_data[0]:.4f} | Right wrist X: {right_data[0]:.4f}")
            except OSError as e:
                print(f"[net] send failed: {e}")
                sock.close()
                sock = reconnect_with_backoff(UNOQ_IP, UNOQ_PORT)
                print("[net] reconnected")

        cv2.imshow("HapticTalk Bridge", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HapticTalk MediaPipe bridge")
    parser.add_argument("--selftest", action="store_true",
                         help="connect, send one test frame, and exit")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(run_selftest(UNOQ_IP, UNOQ_PORT))
    else:
        main()
