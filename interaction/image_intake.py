"""interaction/image_intake.py — Reference image intake for a session.

Saves uploaded reference images to the session output directory and provides
retrieval. Images confirm shape/topology only; they never gate dimensions.
"""
from __future__ import annotations
import os
import shutil


def save_reference_image(source_path: str, session_dir: str) -> str:
    """Save a reference image to the session's output directory.
    Returns the saved image path, or empty string on failure."""
    if not os.path.isfile(source_path):
        return ""
    os.makedirs(session_dir, exist_ok=True)
    dest = os.path.join(session_dir, "00_reference_image.png")
    shutil.copy2(source_path, dest)
    return dest


def get_reference_image(session_dir: str) -> str | None:
    """Return the saved reference image path, or None if none exists."""
    ref_path = os.path.join(session_dir, "00_reference_image.png")
    if os.path.isfile(ref_path):
        return ref_path
    return None


def has_reference_image(session_dir: str) -> bool:
    """Check whether a reference image has been saved for this session."""
    return os.path.isfile(os.path.join(session_dir, "00_reference_image.png"))