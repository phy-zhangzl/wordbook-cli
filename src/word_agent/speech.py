"""Speech playback helpers."""

from __future__ import annotations

import shutil
import subprocess
import sys


def speech_supported() -> bool:
    return sys.platform == "darwin" and shutil.which("say") is not None


def speak_word(word: str, rate: int | None = None, voice: str | None = None) -> bool:
    if not word:
        return False
    if not speech_supported():
        return False
    command = ["say"]
    if voice:
        command.extend(["-v", voice])
    if rate is not None:
        command.extend(["-r", str(rate)])
    command.append(word)
    try:
        subprocess.run(command, check=True)
    except (OSError, subprocess.SubprocessError):
        return False
    return True
