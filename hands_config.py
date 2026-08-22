"""
HapticTalk - shared MediaPipe Hands configuration

Runs on your LAPTOP.

record_signs.py (training) and mediapipe_bridge.py (live inference) must use
identical MediaPipe settings, or the landmark coordinates they produce come
from different networks and drift apart. Both should call make_hands() from
here instead of constructing mp.solutions.hands.Hands directly.
"""

import mediapipe as mp


def make_hands(max_num_hands=2):
    return mp.solutions.hands.Hands(
        max_num_hands=max_num_hands,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.3,
        model_complexity=0,
    )
