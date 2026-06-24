"""hestia/runtime.py — the live care session the agent's tools act on.

The agent's tools are plain functions (ADK calls them by name); they operate on
whatever care session the app has set here. The web server points this at its
current HestiaCare on each reset.
"""
from __future__ import annotations

care = None  # set by the app to the active HestiaCare


def set_care(c) -> None:
    global care
    care = c
